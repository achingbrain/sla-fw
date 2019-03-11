## action = print

### jobdir = "no project"
jméno projektu

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

### calibrateRegions = 0
počet kalibračních oblastí (2, 4, 6, 8, 9), 0 = off

### calibrateTime = expTime
počet vteřin, kolik se přidá na každé kalibrační oblasti, může být float

### calibrateInfoLayers = 10
počet vrstev od začátku, do kterých se bude generovat informace o době osvitu (pad se nepočítá?)
