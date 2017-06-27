#!/bin/bash

rand() {
	floor=`echo "$1" | cut -d "-" -f 1`
	ceil=`echo "$1" | cut -d "-" -f 2`
	num=$RANDOM #Pseudorandom value
	let "num %= $ceil - $floor + 1"
	let "num += $floor"
	echo "$num"
}

execute() {
	numJobs=$1
	timePerJob=$2
	cat > job.sh <<-EOF
	#!/bin/bash
	echo "Starting"
	sleep $timePerJob
	echo "Done"
	EOF
	while [ "$numJobs" -gt 0 ]; do
		let "numJobs -= 1"
		sbatch job.sh
	done
}

uptime() {
        cat /proc/uptime | awk '{print $1}' | cut -d '.' -f 1 # In seconds, rounded down
}

usage() {
	echo "Usage:"
	echo "-w                            wait time between job submissions"
	echo "-c --continuous <iterations>  repeat job submission <iterations> times"
	echo "-n <number>                   the number of jobs submitted (X or X-Y for range)"
	echo "-d <duration>                 the duration of each job (X or X-Y for range)"
	echo "-h                            print this help message and exit"
}

WAIT=10
CONTINUOUS=1
NUMBER=10
DURATION=20
ARGS=`getopt -n clic-test -o w:hc:n:d: --long continuous: -- "$@"`
if [ $? != 0 ] ; then
	usage
	exit 1
fi
eval set -- "$ARGS"
while true; do
	case $1 in
		-w)
			WAIT="$2"
			shift 2
			;;
		-h)
			usage
			exit 0
			;;
		-c | --continuous)
			CONTINUOUS="$2"
			shift 2
			;;
		-n)
			NUMBER="$2"
			shift 2
			;;
		-d)
			DURATION=$2
			shift 2
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

startTime=`uptime`
echo "# Submits $NUMBER $DURATION second jobs every 10 seconds for $CONTINUOUS iterations" > out
echo "time jobsQueued jobsRunning nodesUp" >> out

submit() {
	while :; do
		if [ "$CONTINUOUS" -gt 0 ]; then
			execute `rand $NUMBER` `rand $DURATION`
			let "CONTINUOUS -= 1"
		else
			break
		fi
	        sleep $WAIT
	done
}

record() {
	minRunItr=5
	while :; do
		let "minRunItr -= 1"
	        rCount=`squeue -h -t r,cg,cf -o %A | wc -l`
	        qCount=`squeue -h -t pd -o %A | wc -l`
	        nodesUp=`gcloud compute instances list | tail -n+3 | wc -l`
	        curTime=$(expr $(uptime) - $startTime)
	        echo "$curTime $qCount $rCount $nodesUp" >> out
		sleep 10
	        if [ $qCount -eq 0 ] && [ $rCount -eq 0 ] && [ $nodesUp -eq 0 ] && [ $minRunItr -le 0 ]; then
	                break
	        fi
	done
}

submit &
record &
