#!/bin/sh

export LANG=C.UTF-8
FLASK_APP=server.py flask run --host=0.0.0.0 &
start_indy_node Node1 0.0.0.0 9701 0.0.0.0 9702
