from flask import Flask
from flask import Response

app = Flask(__name__)


@app.route('/init')
def get_genesis():
    with open('/var/lib/indy/prifob/pool_transactions_genesis', 'r') as manifest:
        genesis = manifest.read(int(1E9))
        return Response(genesis, mimetype='text/plain')


@app.route('/domain')
def get_domain():
    with open('/var/lib/indy/prifob/domain_transactions_genesis', 'r') as manifest:
        domain = manifest.read(int(1E9))
        return Response(domain, mimetype='text/plain')
