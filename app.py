import time, os, dns.resolver,logging, boto3, signal,ipaddress
from flask import Flask, jsonify, request, Response
from prometheus_client import Counter, generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
from logging.handlers import RotatingFileHandler
from botocore.exceptions import NoCredentialsError, PartialCredentialsError



app = Flask(__name__)


## Setup access logs 

handler = RotatingFileHandler('access.log', maxBytes=10000, backupCount=3)
handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
app.logger.addHandler(handler)

#Before each request is executed by the routes, this function will log it.
@app.before_request
def log_request_info():
    app.logger.info(f'{request.remote_addr} - {request.method} - {request.path} - {request.data.decode("utf-8")}')





# Error handler for bad requests
@app.errorhandler(400)
def bad_request(error):
    return jsonify({"message": "You have sent a bad request, please verify the API parameters"}), 400


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




#Logging initialize
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)




#Setup Dynamodb

dynamodb = boto3.resource('dynamodb', region_name = "ap-south-1", aws_access_key_id=(os.environ['AWS_ACCESS_KEY_ID']), aws_secret_access_key=(os.environ['AWS_SECRET_ACCESS_KEY']))
table_name = os.getenv('DYNAMODB_TABLE', 'veeren') 
table = dynamodb.Table(table_name)


def infinite_counter(start=1):
    n = start
    while True:
        yield n
        n += 1

counter = infinite_counter(start=1)





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
@app.route('/v1/tools/lookup', methods=['GET'])
def lookup():
    domain = request.args.get('domain')
    if not domain:
        return jsonify({'error': 'Domain parameter is required'}), 400

    try:
        # Resolve IPv4 addresses
        answers = dns.resolver.resolve(domain, 'A')
        ipv4_addresses = [rdata.address for rdata in answers]
    except Exception as e:
        logger.error(f"Error resolving domain {domain}: {e}")
        return jsonify({'error': str(e)}), 500

    if ipv4_addresses:
        # Generate the next entry number
        entry_number = next(counter)

        # Log successful query to DynamoDB
        log_entry = {
            'entry_number': str(entry_number),
            'domain': domain,
            'ipv4_addresses': ipv4_addresses
        }

        try:
            # Insert the log entry into DynamoDB
            table.put_item(Item=log_entry)
            logger.info(f"Successfully resolved domain {domain}: {ipv4_addresses}")
            return jsonify({'domain': domain, 'ipv4_addresses': ipv4_addresses, 'entry_number': entry_number})
        except (NoCredentialsError, PartialCredentialsError):
            logger.error("AWS credentials not found.")
            return jsonify({'error': 'AWS credentials not found'}), 500
        except Exception as e:
            logger.error(f"Error inserting log entry into DynamoDB: {e}")
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'domain': domain, 'ipv4_addresses': []})




@app.route('/v1/history', methods=['GET'])
def queries():
    try:
       
        response = table.scan()
        items = response['Items']
        
        # Convert entry_number to an integer for sorting and get last 20 entries
        items = sorted(items, key=lambda x: int(x['entry_number']), reverse=True)
        last_20_items = items[:20]

        return jsonify(last_20_items)
    except Exception as e:
        logger.error(f"Error fetching queries: {e}")
        return jsonify({'error': str(e)}), 500




@app.route("/shutdown")
def shutdown():
    # this mimics a CTRL+C hit by sending SIGINT
    # it ends the app run, but not the main thread
    pid = os.getpid()
    os.kill(pid, signal.SIGINT)
    return "Shutting down application", 200

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0', port=3000)
