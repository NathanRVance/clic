#!/bin/bash

usage() {
        echo "Usage:"
	echo "-r --running    report nodes that are currently running (default includes booting and shutting down)"
	echo "-h --help       print this help message"
}

running=false
ARGS=`getopt -n clic-nodesup -o hr --long help,running -- "$@"`
if [ $? != 0 ] ; then
        usage
        exit 1
fi
eval set -- "$ARGS"
while true; do
	case $1 in
		-h | --help)
                        usage
                        exit 0
                        ;;
		-r | --running)
			running=true
			shift
			;;
		--)
			shift
			break
			;;
		*)
			break
			;;
	esac
done

responds() {
	host=$1
	cmdpid=$BASHPID
	(
		sleep 1
		kill -PIPE $cmdpid &> /dev/null
		if [ $? == 0 ]; then
			echo false
		fi
	) &
	while ssh -i KEY -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null USER@$host exit &> /dev/null; do
		echo true
		exit
	done
	echo false
}

getResponds() {
	hosts=$1
	for node in $hosts; do
		{ if [ "`responds $node`" == true ]; then
			echo $node
		fi } &
	done
}

cloudReport="`gcloud compute instances list 2>&1 | tail -n+2`"
if [ -z "$cloudReport" ]; then exit; fi
if [ "$running" == "true" ]; then
	cloudReport="`echo "$cloudReport" | grep "RUNNING" | awk '{print $1}'`"
	echo "`getResponds "$cloudReport"`"
else
	echo "$cloudReport" | awk '{print $1}'
fi
