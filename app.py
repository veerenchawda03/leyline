import time, os, dns.resolver,logging, boto3, signal,ipaddress
from flask import Flask, jsonify, request, Response
from prometheus_client import Counter, generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
from logging.handlers import RotatingFileHandler
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from threading import Lock



app = Flask(__name__)


## Setup access logs 

#Logging initialize
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


handler = RotatingFileHandler('access.log', maxBytes=10000, backupCount=3)
handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
app.logger.addHandler(handler)


active_requests = 0
request_lock = Lock()
shutdown_in_progress = False


#Before each request is executed by the routes, this function will log it. 

@app.before_request
def track_active_requests():
    global active_requests, shutdown_in_progress
    if shutdown_in_progress and request.path != "/shutdown":
        # If shutdown is in progress, reject new requests (except for /shutdown)
        return jsonify({"message": "We are shutting down the server for maintenance. Please try again later."}), 503
    
    with request_lock:
        active_requests += 1
    app.logger.info(f'{request.remote_addr} - {request.method} - {request.path} - {request.data.decode("utf-8")}')
    app.logger.info(f'Active requests count increased: {active_requests}')

@app.after_request
def track_finished_requests(response):
    global active_requests
    if request.path == "/shutdown":
        return response
    
    with request_lock:
        active_requests -= 1
    app.logger.info(f'Response Status: {response.status_code} - {response.data.decode("utf-8")}')
    app.logger.info(f'Active requests count decreased: {active_requests}')
    return response




#Following function is to support the /metrics route
registry = CollectorRegistry()

request_counter = Counter(
    'flask_app_requests_total', 
    'Total number of requests to the Flask app', 
    ['method', 'endpoint'],
    registry=registry
)

# /home endpoint to return a request counter, so any number of requests will be stored in here and made available to /metrics

@app.route('/home')
def index():
    request_counter.labels(method='GET', endpoint='/home').inc()
    return 'Hello, World!'

# Created the /metrics endpoint for Prometheus to scrape
@app.route('/metrics')
def metrics():
    data = generate_latest(registry)
    return Response(data, mimetype=CONTENT_TYPE_LATEST)



# /health endpoint to return 200 http code
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200


# / (root) endpoint to return unix epoch

is_kubernetes = False
if os.getenv('KUBERNETES_SERVICE_HOST'):      #https://kubernetes.io/docs/tasks/run-application/access-api-from-pod/#directly-accessing-the-rest-api.
    is_kubernetes = True

@app.route('/')
def root():

    response = {
        "version": "1.0.0",
        "date": int(time.time()),
        "kubernetes": is_kubernetes
    }
    return jsonify(response)


#Setup Dynamodb

dynamodb = boto3.resource('dynamodb', region_name = "ap-south-1", aws_access_key_id=(os.environ['AWS_ACCESS_KEY_ID']), aws_secret_access_key=(os.environ['AWS_SECRET_ACCESS_KEY']))
table_name = os.getenv('DYNAMODB_TABLE', 'veeren') 
table = dynamodb.Table(table_name)





#Endpoint to validate if IPv4

@app.route('/v1/tools/validate', methods=['GET'])
def validate():
    # Get the 'ip' parameter from the query string
    ip = request.args.get('ip')
    
    if ip is None:
        return jsonify({"error": "No IP address provided"}), 400

    try:
        ipaddress.IPv4Address(ip)
        return jsonify({"message": "Valid IPv4 address"}), 200
    except ipaddress.AddressValueError:
        return jsonify({"message": "Invalid IPv4 address"}), 400
    




# Endpoint to resolve IPv4 addresses
counter = iter(range(1, 1000000))

@app.route('/v1/tools/lookup', methods=['GET'])
def lookup():
    domain = request.args.get('domain')
    
    # Handle missing domain query parameter (400 Bad Request)
    if not domain:
        return jsonify({'message': 'Domain parameter is required'}), 400

    try:
        # Resolve IPv4 addresses
        answers = dns.resolver.resolve(domain, 'A')
        ipv4_addresses = [rdata.address for rdata in answers]
    except dns.resolver.NXDOMAIN:
        #  domain does not exist (404 Not Found)
        logger.error(f"Domain {domain} not found.")
        return jsonify({'message': 'Domain not found'}), 404
    except dns.resolver.NoAnswer:
        # no A record is found for the domain (404 Not Found)
        logger.error(f"No A record found for domain {domain}.")
        return jsonify({'message': 'No A record found for domain'}), 404
    except Exception as e:
        # Handle other generic errors (500 Internal Server Error)
        logger.error(f"Error resolving domain {domain}: {e}")
        return jsonify({'message': str(e)}), 500

    if ipv4_addresses:
        # Generate the next entry number (queryID)
        queryID = next(counter)
        
        # Get the client's IP address (assuming request has a 'REMOTE_ADDR' header)
        client_ip = request.remote_addr or '0.0.0.0'

        # Capture the current timestamp (epoch time)
        created_time = int(time.time())

        # Log successful query to DynamoDB
        log_entry = {
            'queryID': queryID,
            'domain': domain,
            'client_ip': client_ip,
            'created_time': created_time,
            'addresses': [{'ip': ip, 'queryID': queryID} for ip in ipv4_addresses]
        }

        try:
            # Insert the log entry into DynamoDB
            table.put_item(Item=log_entry)
            logger.info(f"Successfully resolved domain {domain}: {ipv4_addresses}")
            
            # Prepare the response
            response = {
                'domain': domain,
                'addresses': [{'ip': ip, 'queryID': queryID} for ip in ipv4_addresses],
                'client_ip': client_ip,
                'created_time': created_time,
                'queryID': queryID
            }
            
            return jsonify(response), 200
        except (NoCredentialsError, PartialCredentialsError):
            logger.error("AWS credentials not found.")
            return jsonify({'message': 'AWS credentials not found'}), 500
        except Exception as e:
            logger.error(f"Error inserting log entry into DynamoDB: {e}")
            return jsonify({'message': str(e)}), 500
    else:
        return jsonify({'message': 'No IP addresses found for the domain'}), 404





@app.route('/v1/history', methods=['GET'])
def queries():
    try:
        # Fetch all items from the DynamoDB table
        response = table.scan()
        items = response.get('Items', [])
        
        # Sort the items by 'queryID' (which is the 'entry_number') and get the last 20 entries
        sorted_items = sorted(items, key=lambda x: int(x['queryID']), reverse=True)
        last_20_items = sorted_items[:20]

        # Format the last 20 items to match the required response format
        formatted_items = []
        for item in last_20_items:
            formatted_item = {
                'domain': item['domain'],
                'addresses': [{'ip': addr['ip'], 'queryID': int(addr['queryID'])} for addr in item.get('addresses', [])],
                'client_ip': item.get('client_ip', '0.0.0.0'),
                'created_time': int(item.get('created_time', 0)),
                'queryID': int(item['queryID'])
            }
            formatted_items.append(formatted_item)

        return jsonify(formatted_items)
    except Exception as e:
        logger.error(f"Error fetching queries: {e}")
        return jsonify({'error': str(e)}), 500




# use this endpoint to gracefully shutdown the app





@app.route("/shutdown")
def shutdown():
    global active_requests, shutdown_in_progress
    with request_lock:
        shutdown_in_progress = True
        if active_requests > 0:
            app.logger.info(f"Cannot shut down, active requests in progress: {active_requests}")
            return jsonify({
                "message": "Cannot shut down, active requests in progress",
                "active_requests": active_requests
            }), 400

        app.logger.info("No active requests, shutting down the application.")
        os.kill(os.getpid(), signal.SIGTERM)
        
        return "Shutting down application", 200

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0', port=3000)
