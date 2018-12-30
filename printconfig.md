## action = print

### jobdir = "no project"
jméno projektu

### direct = off
on - rovnou zahájí tisk

### autoOff = on
off - po ukončení nevypíná tiskárnu

### expTime = 8.0
doba osvitu [s]

### expTime2 = expTime
doba osvitu 2 [s]

### expTime3 = expTime
doba osvitu 3 [s]

### expTimeFirst = 35
doba osvitu prvních tří vrstev [s]

### layerHeight
výška vrstvy [mm], pokud je uvedeno, nahrazuje stepNum

### layerHeight2 = layerHeight
výška vrstvy 2 [mm], podmíněno přítomností layerHeight

### layerHeight3 = layerHeight
výška vrstvy 3 [mm], podmíněno přítomností layerHeight

### stepNum = 40
počet kroků na vrstvu; 40 = 0.05 mm

### stepNum2 = stepNum
počet kroků na vrstvu 2

### stepNum3 = stepNum
počet kroků na vrstvu 3

### slice2 = 9999998
vrstva přechodu na parametry 2

### slice3 = 9999999
vrstva přechodu na parametry 3

### numFade = 10 [3;20]
počet přechodných vrstev mezi expTimeFirst a expTime [vrstvy]

### tiltDelayBefore = 0.0
prodleva mezi osvitem a sklopením tiltu [s]

### tiltDelayAfter = 0.0
prodleva mezi přiklopením tiltu a osvitem [s]

### upAndDownWait = 10
doba čekání při up&down [s]

### upAndDownEveryLayer = 0
dělat up&down každých x vrstev, 0 vypne

### tilt = on
off - při změně vrstvy nesklápí vaničku ale hýbe platformou nahoru a dolů

### fakeTiltUp = 5
o kolik zvedat platformu při tilt=off [mm]

### calibrateRegions = 0
počet kalibračních oblastí (2, 4, 6, 8, 9), 0 = off

### calibrateTime = expTime
počet vteřin, kolik se přidá na každé kalibrační oblasti, může být float

### calibrateInfoLayers = 10
počet vrstev od začátku, do kterých se bude generovat informace o době osvitu (pad se nepočítá?)
