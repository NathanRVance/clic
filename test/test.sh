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
	# Both arguments are ranges
	numJobs=`rand $1`
	timePerJob=$2
	curTime=$(expr $(uptime) - $startTime)
	while [ "$numJobs" -gt 0 ]; do
		sleepTime=`rand $timePerJob`
		echo -e "#!/bin/bash\necho 'Starting'\nsleep $sleepTime\necho 'Done'" | sbatch
		echo "# Submitted sleep $sleepTime at t=$curTime" >> out
		let "numJobs -= 1"
	done
}

uptime() {
        cat /proc/uptime | awk '{print $1}' | cut -d '.' -f 1 # In seconds, rounded down
}

usage() {
	echo "Usage:"
	echo "-w <time>                     wait time between job submissions"
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
echo "# Submits $NUMBER $DURATION second jobs every $WAIT seconds for $CONTINUOUS iterations" > out
echo "time jobsQueued jobsRunning nodesUp jobsSubmitted" >> out

submit() {
	while :; do
		if [ "$CONTINUOUS" -gt 0 ]; then
			execute $NUMBER $DURATION
			let "CONTINUOUS -= 1"
		else
			break
		fi
	        sleep $WAIT
	done
}

record() {
	submitPID=$1
	while :; do
	        rCount=`squeue -h -t r,cg,cf -o %A | wc -l`
	        qCount=`squeue -h -t pd -o %A | wc -l`
	        nodesUp=`gcloud compute instances list | tail -n+3 | wc -l`
	        curTime=$(expr $(uptime) - $startTime)
	        echo "$curTime $qCount $rCount $nodesUp" >> out
		sleep 10
	        if ! `kill -0 $submitPID &> /dev/null` && [ $qCount -eq 0 ] && [ $rCount -eq 0 ] && [ $nodesUp -eq 0 ]; then
			fixStuff
	                break
	        fi
	done
}


fixStuff() {
	mod () {
		local t=$1
		local num=$2
		bestT=-1
		# Find the time closest to t in file
		while read line; do
			if [[ $line =~ ^[0-9].*$ ]]; then
				lineT=`echo $line | awk '{print $1}'`
				if [ $lineT -le $t ] || [ $bestT -eq -1 ]; then bestT=$lineT
				else break
				fi
			fi
		done <<< `cat $file`
		# Modify that line
		echo "fixing t=$bestT: $num"
		sed -i "s/^$bestT \(.*\)/$bestT \1 $num/" $file
	}
	
	lastT=0
	num=0
	sleepDat="`grep "# Submitted sleep" long2 | sed 's/# Submitted sleep \([0-9]*\) at t=\([0-9]*\)/\2 \1/'`"
	while read i; do
		t=`echo $i | awk '{print $1}'`
		if [ $t -le `expr $lastT + 5` ]; then
			let "num += 1"
		else
			mod $lastT $num
			lastT=$t
			num=1
		fi
	done <<< $sleepDat
	mod $lastT $num

	#Fill in zeros
	sed -i 's/^\([0-9]*\) \([0-9]*\) \([0-9]*\) \([0-9]*\)$/\1 \2 \3 \4 0/' $file
}

submit &
record $! &
