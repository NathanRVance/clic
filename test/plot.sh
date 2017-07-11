#!/bin/bash

file=$1

gnuplot -persist << EOF
set   autoscale                        # scale axes automatically
unset log                              # remove any log-scaling
unset label                            # remove any previous labels
set xtic auto                          # set xtics automatically
set ytic auto                          # set ytics automatically
set title "Virtual Custer Utilization over Time"
set xlabel "Time (seconds)"
set ylabel "Virtual Cluster Utilization"
set xrange [10:]
set key
plot    "$file" using 1:2 title 'Jobs Queued' with linespoints , \
        "$file" using 1:3 title 'Jobs Running' with linespoints , \
        "$file" using 1:4 title 'Nodes Up' with linespoints , \
        "$file" using 1:5 title 'Jobs submitted' with linespoints
EOF
