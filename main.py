import raid6


drive_path = r'drives'
file_src = r'files'
iterations = 10000 # Change this to change how long time it runs



cont = raid6.Raid6Controller(8,10000,drive_path,file_src)
for _ in range(iterations):
    cont.detect_new_file()
    cont.detect_failed_drives()
    if cont.failed_drives:
        cont.fix_failure()

for key in cont.file_metadata:
    cont.read_file(key)