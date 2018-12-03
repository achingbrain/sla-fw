patternFields = 8;

plateX = 120;
plateY = 68;

labelX = 5;
labelY = 8;
labelPadX = 1.5 * labelX;
labelPadY = 1.5 * labelY;
patternHeight = 0.150;
labelHeight = patternHeight + 0.5;
patternWall = 1;
finalRotate = -90;


splits = [
[ -1, -1],
[ -1, -1],
[ 2, 1],
[ -1, -1],
[ 2, 2],
[ -1, -1],
[ 3, 2],
[ -1, -1],
[ 4, 2],
[ 3, 3],
];

*color("white") cube([plateX, plateY, 0.01]);

count = splits[patternFields];
echo(count[0], count[1]);

px = 0;
py = 0;
x = plateX / count[0];
y = plateY / count[1];
rotate([0, 0, finalRotate])
for (px = [0 : x : plateX-1]) {
	for (py = [0 : y : plateY-1]) {
		translate([px, py, 0]) union() {
			translate([0, (y - labelPadY) / 2]) union() {
				cube([labelPadX, labelPadY, patternHeight]);
				translate([(labelPadX - labelX) / 2, (labelPadY - labelY) / 2, 0])
					cube([labelX, labelY, labelHeight]);
			}
			difference() {
				cube([x, y, patternHeight]);
				translate([patternWall / 2, patternWall / 2, -0.05])
					cube([x - patternWall, y - patternWall, patternHeight + 0.1]);
			}
		}
	}
}
