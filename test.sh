#!/bin/bash

echo "time jobsQueued jobsRunning nodesUp" > out

cat > job.sh << EOF
#!/bin/bash
sleep 100
EOF

for i in `seq 1 10`; do
        qsub job.sh
done

sleep 10

uptime() {
        cat /proc/uptime | awk '{print $1}' | cut -d '.' -f 1 # In seconds, rounded down
}

startTime=`uptime`

while :; do
        rCount=`qstat -r | tail -n+6 | wc -l`
        qCount=`qstat -i | tail -n+6 | wc -l`
        nodesUp=`gcloud compute instances list | tail -n+3 | wc -l`
        curTime=$(expr $(uptime) - $startTime)
        echo "$curTime $qCount $rCount $nodesUp" >> out
        if [ $qCount -eq 0 ] && [ $rCount -eq 0 ] && [ $nodesUp -eq 0 ]; then
                break
        fi
        sleep 10
done
