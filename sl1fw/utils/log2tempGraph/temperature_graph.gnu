#set term qt font "arial,16" size 1600,900
set term svg font "arial,16" size 1600,900
set output '/dev/stdout'

set ylabel "Temperature [°C]"
set xlabel "Project time [HH:MM]"

set xdata time
set timefmt "%s"
set format x "%H:%M"

set grid xtics ytics mytics
set mytics 2
set grid

plot \
	'/dev/stdin' u 1:4 w l title "Tower", \
	'/dev/stdin' u 1:5 w l title "Tilt", \
	'/dev/stdin' u 1:2 w l title "UV", \
	'/dev/stdin' u 1:3 w l title "Ambient"
