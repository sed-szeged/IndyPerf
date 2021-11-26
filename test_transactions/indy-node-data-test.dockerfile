FROM bcgovimages/von-image:node-1.12-3

USER root
WORKDIR /
RUN apt-get update -y && apt-get install -y \
        git \
        curl

RUN git clone https://github.com/hyperledger/indy-sdk

COPY test_transactions.py /indy-sdk/samples/python/src
COPY utils.py /indy-sdk/samples/python/src/utils.py
RUN curl http://35.228.96.2:5000/init --output /indy-sdk/samples/python/src/genesis.txt

WORKDIR /indy-sdk/samples/python
RUN python -m src.test_transactions
