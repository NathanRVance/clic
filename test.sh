#!/bin/bash

rand() {
	floor=$1
	ceil=$2
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

startTime=`uptime`
echo "time jobsQueued jobsRunning nodesUp" > out
touch addingJobs
while :; do
	if [ -e addingJobs ]; then
		execute `rand 0 3` `rand 1 50` #Add 0-3 sleep 1-50 jobs to the queue
	fi
        sleep 10
        rCount=`qstat -r | tail -n+6 | wc -l`
        qCount=`qstat -i | tail -n+6 | wc -l`
        nodesUp=`gcloud compute instances list | tail -n+3 | wc -l`
        curTime=$(expr $(uptime) - $startTime)
        echo "$curTime $qCount $rCount $nodesUp" >> out
        if [ $qCount -eq 0 ] && [ $rCount -eq 0 ] && [ $nodesUp -eq 0 ]; then
                break
        fi
done
