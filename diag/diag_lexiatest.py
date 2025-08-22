from oleodiag.diag_translations import diag_translations
import csv

trs = diag_translations(lang="GB",path="DUL/")

csvfile = open("dat_pp/DESCTLCH.csv", newline='')
cs = csv.reader(csvfile, delimiter=',', quotechar='"')         
for f in cs:
    if f[0] == "VEHICULE":
        continue

    model = f[0]
    ref = f[3]
    desc = f[4]
    print(model + ": " + trs.decodalate(desc) + " (" + ref + ")")
csvfile.close()