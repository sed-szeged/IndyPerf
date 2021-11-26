FROM ubuntu:16.04
RUN apt-get update -y && apt-get install -y \
        git \
        curl \
        python3.5 \
        python3-pip \
        python-setuptools \
        python3-nacl \
        apt-transport-https \
        ca-certificates \
        supervisor
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys CE7709D068DB5E88 && \
bash -c 'echo "deb https://repo.sovrin.org/deb xenial stable" >> /etc/apt/sources.list' && \
apt-get update && \
apt-get install -y indy-node

COPY ./indy-node-start-new.sh .
RUN chmod 777 ./indy-node-start-new.sh

COPY scripts/indy_config.py /etc/indy/
RUN mkdir /var/lib/indy/prifob

RUN curl http://35.228.96.2:5000/init --output /var/lib/indy/prifob/pool_transactions_genesis
RUN curl http://35.228.96.2:5000/domain --output /var/lib/indy/prifob/domain_transactions_genesis

RUN init_indy_node Node5 0.0.0.0 9701 0.0.0.0 9702 0000000000000000000000000NewNode

CMD ["./indy-node-start-new.sh"]