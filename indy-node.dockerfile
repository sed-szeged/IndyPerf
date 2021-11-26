FROM ubuntu:16.04
ENV FLASK_APP=server.py
# Install environment
RUN apt-get update -y && apt-get install -y \
        git \
        python3.5 \
        python3-pip \
        python-setuptools \
        python3-nacl \
        apt-transport-https \
        ca-certificates \
        supervisor
RUN pip3 install -U \
        pip==9.0.3 \
        setuptools
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys CE7709D068DB5E88 && \
bash -c 'echo "deb https://repo.sovrin.org/deb xenial stable" >> /etc/apt/sources.list' && \
apt-get update && \
apt-get install -y indy-node

COPY server.py .
COPY indy-node-start.sh .
COPY requirements.txt requirements.txt
COPY scripts/indy_config.py /etc/indy/
RUN chmod 777 ./indy-node-start.sh
RUN pip install -r requirements.txt
RUN generate_indy_pool_transactions --nodes 4 --clients 5 --nodeNum 1 --ips '13,35.241.189.121,35.193.142.40,34.70.121.220' --network=prifob
#RUN generate_indy_pool_transactions --nodes 8 --clients 5 --nodeNum 1 --ips '34.65.46.128,35.202.145.142,35.238.185.183,35.187.50.167,34.118.10.158,34.65.234.44,34.127.92.19,34.125.251.88' --network=prifob

CMD ["./indy-node-start.sh"]