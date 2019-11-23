# Raid6

This is the implementation of Raid 6 file storeage system. The drives are simulated as Numpy arrays stored on the computers "real" drive. The program can handle .txt and .png files. For .png files only square shaped images work. Keep in mind that the program is really slow so use small images only (less than 100x100). 

You are going to need the package pyfinite available here: https://github.com/emin63/pyfinite
Besides you also need Python Image Library (PIL) and tqdm package (for progress bar) and standard Python stuff like Numpy, Matplotlib etc.


To use the program:

1. Download this repo
2. Run the script "main.py"
3. In the "files" folder you can add files. The program detects them automatically. There is already a small image in the folder.
4. To simulate a drive failure, go to the "drives" folder and delete 1 or 2 drives. The program automatically detects the failure and starts restoring the data. Don't delete more than 2 drives at once. Once you have deleted a drive don't delete another one until the program has finished restoring the data.  
5. The program runs for a set amount of iterations. After it has finished it reads all the files back. If it is a .png it displays the image, if it is .txt it prints all the elements. You can change the number of iterations in "main.py"

Note the program does not really have any error handling and it is a bit buggy.
