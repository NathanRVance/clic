#!/bin/bash

# NAMESCHEME is the name of the head node, and all NAMESCHEMEXX are compute nodes.

LOGFILE="/var/log/clic.log"
TWIDDLE_TIME=15
SLEEP_TIME=10
MAX_NODE_NUM=99

mainLoop() {
	while [ "true" ]; do
		clic-sync-hosts
		resolveIPs
		# Queued and running jobs are one line each containing the job number
		rJobs=`squeue -h -t r,cg,cf -o %A`
		qJobs=`squeue -h -t pd -o %A`

		nodesWanted=0
		nodesUp=0
		nodesBooting=0
		for node in $(seq -w 1 $MAX_NODE_NUM); do
			if [ "`state $node`" == "R" ]; then
				nodesUp=`expr $nodesUp + 1`
			elif [ "`state $node`" == "C" ]; then
				nodesBooting=`expr $nodesBooting + 1`
			fi
		done
		for jobNum in $qJobs; do
			# Keep track of time jobs have been queued
			if [ -z ${job[$jobNum]} ]; then job[$jobNum]=0; fi
			job[$jobNum]=`expr ${job[$jobNum]} + $SLEEP_TIME`
			# Determine if we need another node
			if [[ "$nodesBooting" -eq 0 && ( "${job[$jobNum]}" -gt "$TWIDDLE_TIME" || "$nodesUp" -eq 0 ) ]]; then
				nodesWanted=`expr $nodesWanted + 1`
			fi
		done
		nodesIdle=`numIdle`
		echo "Nodes wanted: $nodesWanted, Nodes up: $nodesUp, Nodes idle: $nodesIdle Nodes booting: $nodesBooting" >> $LOGFILE # skip stdout so we don't gum up /var/log/messages
		# Check that the nodes wanted aren't currently booting (nodesWanted + jobsRunning > nodesUp)
		nodesWanted=$((($nodesWanted - $nodesBooting + 1) / 2))
		#if [ $nodesWanted -gt 10 ]; then nodesWanted=10; fi #cap it at 10
		nodesWanted=$(($nodesWanted - $nodesIdle))
		create $nodesWanted

		# Check for nodes to delete
		if [ "$nodesIdle" -gt "0" ]; then
			# Node(s) sit idle...
			if [ -z "$emptyTime" ]; then
				emptyTime=`uptime`
			elif [ "$(expr $(uptime) - $emptyTime)" -gt "$TWIDDLE_TIME" ]; then
				# ...and have sat idle for some time
				numToDelete=$((($nodesIdle + 1) / 2))
				delete $numToDelete
				emptyTime=""
			fi
		elif [ -n "$emptyTime" ]; then
			# Clean up
			emptyTime=""
		fi

		# Book keeping
		# States : <C|R|D>
		# C=creating, R=running, D=deleting
		# Null string for deleted nodes
		nodenamesUp="`upNodes`" # As reported by slurm
		cloudReportedRunning="`clic-nodesup -r`"
		cloudReportedAll="`clic-nodesup`"
		nodesWentDown=false
		for node in $(seq -w 1 $MAX_NODE_NUM); do
			# Routine stuff
			if [ "`state $node`" == "C" ] && [ -n "`grep NAMESCHEME$node <<< $cloudReportedRunning`" ]; then
				# Node was creating, now is running
				echo "Node NAMESCHEME$node came up" | tee -a $LOGFILE
				nodeInit $node
				scontrol update nodename=NAMESCHEME$node state=resume
				setState $node R
			elif [ "`state $node`" == "D" ] && [ -z "`grep NAMESCHEME$node <<< $cloudReportedAll`" ]; then
				# Node was deleting, now is gone
				echo "Node NAMESCHEME$node went down" | tee -a $LOGFILE
				scontrol update nodename=NAMESCHEME$node state=down reason="Deleted"
				setState $node ""
				nodesWentDown=true

			# Error conditions
			elif [ "`state $node`" == "R" ] && [ -z "`grep NAMESCHEME$node <<< $cloudReportedRunning`" ]; then
				# We think the node is running, but the cloud doesn't
				echo "ERROR: Node NAMESCHEME$node deleted outside of clic!" | tee -a $LOGFILE
				scontrol update nodename=NAMESCHEME$node state=down reason="Error"
				setState $node ""
			elif [ "`state $node`" == "R" ] && [ -n "`grep NAMESCHEME$node <<< $cloudReportedRunning`" ] && [ -z "`grep NAMESCHEME$node <<< $nodenamesUp`" ]; then
				# We think it should be running, and so does the cloud, but Slurm doesn't
				echo "ERROR: Node NAMESCHEME$node is unresponsive" | tee -a $LOGFILE
				deleteInstance $node
			elif [ -z "`state $node`" ] && [ -n "`grep NAMESCHEME$node <<< $cloudReportedRunning`" ]; then
				# Node is running, but isn't registered. Maybe the script was restarted?
				echo "ERROR: Encountered unregistered node NAMESCHEME$node, deleting..." | tee -a $LOGFILE
				deleteInstance $node
			elif [ "`state $node`" == "C" ] && [ "`timeInState $node`" -gt 200 ]; then
				# In create state, and taking way too long
				echo "ERROR: Node NAMESCHEME$node hung on boot" | tee -a $LOGFILE
				echo Y | gcloud compute disks delete NAMESCHEME$node &> /dev/null &
				deleteInstance $node
			fi
		done
		if [ "$nodesWentDown" == "true" ]; then
			# There's a chance they'll come up later with different IPs. Restart slurmctld to avoid errors.
			echo "WARNING: Restarting slurmctld" | tee -a $LOGFILE
			systemctl restart slurmctld.service
		fi

		sleep $SLEEP_TIME
	done
}

uptime() {
	cat /proc/uptime | awk '{print $1}' | cut -d '.' -f 1 # In seconds, rounded down
}

numIdle() {
	local num="`sinfo -h -r -o %A | cut -d '/' -f 2`"	
	if [ -z "$num" ]; then
		echo 0
	else
		echo $num
	fi
}

upNodes() {
	sinfo -h -N -r -o %N
}

state() {
	local node="`echo $1 | sed 's/^0*//'`"
	echo ${nodes[$node]} | awk '{print $1}'
}

timeInState() {
	local node="`echo $1 | sed 's/^0*//'`"
	expr `uptime` - `echo ${nodes[$node]} | awk '{print $2}'`
}

setState() {
	local node="`echo $1 | sed 's/^0*//'`"
	local state="$2"
	if [ -n "$state" ]; then
		nodes[$node]="$state `uptime`"
	else
		nodes[$node]=""
	fi
}

create() {
	local numToCreate=$1
	existingDisks="`gcloud compute disks list | tail -n+2 | awk '{print $1}'`"
	# Determine the next node name to use
	local num
	for num in $(seq -w 1 $MAX_NODE_NUM); do
		if [ "$numToCreate" -le 0 ]; then
			# We're done
			break
		elif [ -z "`state $num`" ]; then
			# This node number is unused
			if [ -n "`grep NAMESCHEME$num <<< $existingDisks`" ]; then
				echo "ERROR: Disk for NAMESCHEME$num exists, but shouldn't! Deleting..." | tee -a $LOGFILE
				echo Y | gcloud compute disks delete NAMESCHEME$num &> /dev/null &
			else
				setState $num C
				scontrol update nodename=NAMESCHEME$num state=resume
				echo "Creating NAMESCHEME$num" | tee -a $LOGFILE
				gcloud compute disks create NAMESCHEME$num --size 10 --source-snapshot NAMESCHEME &> /dev/null &&
				gcloud compute instances create NAMESCHEME$num --machine-type "n1-standard-1" --disk "name=NAMESCHEME$num,device-name=NAMESCHEME$num,mode=rw,boot=yes,auto-delete=yes" &> /dev/null ||
				if [ $? -eq 1 ]; then echo "ERROR: Failed to create NAMESCHEME$num" | tee -a $LOGFILE; fi & #TODO: do something about the failure
				let "numToCreate -= 1"
			fi
		fi
	done
}

delete() {
	local numToDelete=$1
	local idleNodes="`sinfo -o "%t %n" | grep "idle" | awk '{print $2}'`"
	local num
	for num in $(seq -w 1 $MAX_NODE_NUM); do
		if [ "$numToDelete" -le 0 ]; then
			# We're done
			break
		elif [ -n "`grep "NAMESCHEME$num" <<< "$idleNodes"`" ] && [ "`state $num`" == "R" ]; then
			setState $num D
			scontrol update nodename=NAMESCHEME$num state=drain reason="Deleting"
			{
				local n=$num
				while true; do
					if [ -n "`sinfo -h -N -o "%N %t" | grep NAMESCHEME$n | awk '{print $2}' | grep drain`" ]; then
						#It's been drained
						deleteInstance $n
						break
					fi
					sleep 10;
				done
			} &
			let "numToDelete -= 1"
		fi
	done
}

deleteInstance() {
	local num=$1
	echo "Deleting NAMESCHEME$num" | tee -a $LOGFILE
	setState $num D
	scontrol update nodename=NAMESCHEME$num state=down reason="Deleted"
	echo Y | gcloud compute instances delete NAMESCHEME$num &> /dev/null &
}

resolveIPs() {
	if [ "CLOUD" == "false" ]; then
		local ip="`dig +short myip.opendns.com @resolver1.opendns.com`"
		local recordedIP="$(grep "$(hostname -s)$" /etc/hosts | awk '{print $1}')"
		if [ "$ip" != "$recordedIP" ]; then
			for node in `clic-nodesup -r`; do
				num="`echo $node | sed 's/NAMESCHEME//'`"
				if [ -n "$num" ]; then
					nodeInit $num
				fi
			done
			clic-sync-hosts `hostname -s` $ip
		fi
	fi
}

nodeInit() {
	local num=$1
	clic-remote-mount USER@NAMESCHEME$num
}

if [ "`hostname`" == "NAMESCHEME" ] || [ "CLOUD" == "false" ]; then
        # do head node stuff
	rm $LOGFILE
	touch $LOGFILE
	chown `whoami`:`whoami` $LOGFILE
        echo "Starting slurmctld.service" | tee -a $LOGFILE
        systemctl restart slurmctld.service
	if [ "CLOUD" == "true" ]; then
		zone=`gcloud compute instances list | grep "$(hostname) " | awk '{print $2}'`
		echo "Configuring gcloud for zone: $zone" | tee -a $LOGFILE
		gcloud config set compute/zone $zone
	fi
	mainLoop &
else
        # do compute node stuff
	echo "Starting slurmd.service"
        systemctl restart slurmd.service
fi
