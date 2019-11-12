from pyfinite.ffield import FField
from pyfinite.genericmatrix import GenericMatrix
from numpy import array, zeros, append, empty, asarray, roll
import numpy as np
from os.path import join
from time import sleep, time
import os
from multiprocessing import Process
from PIL import Image
from tqdm import tqdm
import concurrent.futures as futures
from multiprocessing import Pool

def func(x):
    return repr(x)

class Raid6Controller():

    
    def __init__(self,num_drives,drive_cap,drives_path,file_src):
        self.num_drives = num_drives
        self.drive_cap = drive_cap
        self.drives_path = drives_path
        self.F = FField(8)
        self.num_stripes = 0
        self.gen_mat = self.build_generator_matrix()
        self.failed_drives = False
        self.drives = [join(drives_path,str(i)+'.npy') for i in range(num_drives)]
        self.init_drives()
        self.available_drives = [1,1,1,1,1,1,1,1]
        self.file_src = file_src
        self.file_metadata = {}
        self.id_counter = 0
        self.files = []
        
    def init_drives(self,drive=None):

        if drive is None:
            init = np.arange(self.num_drives).tolist()
        else:
            init = drive
            
        size = int(np.ceil(np.sqrt(self.drive_cap)))
        for i in init:
            path = self.drives[i]
            arr = zeros((size,size)).astype('uint8')
            np.save(path,arr)
        del arr
        self.drive_dim = size

        
    def build_generator_matrix(self):
        rows = self.num_drives
        cols = self.num_drives - 2
        mat = GenericMatrix(size=(rows,cols),
                            mul=self.F.Multiply, div=self.F.Divide,
                            sub = self.F.Subtract, add=self.F.Add,
                            zeroElement=0, identityElement=1,
                            str = func)
        mat.SetRow(0,[1,0,0,0,0,0])
        mat.SetRow(1,[0,1,0,0,0,0])
        mat.SetRow(2,[0,0,1,0,0,0])
        mat.SetRow(3,[0,0,0,1,0,0])
        mat.SetRow(4,[0,0,0,0,1,0])
        mat.SetRow(5,[0,0,0,0,0,1])
        mat.SetRow(6,[1,1,1,1,1,1])
        mat.SetRow(7,[32,16,8,4,2,1])
        
        return mat
        
    def build_error_generator_matrix(self,rows):
        '''
        Creates a generator matrix for data restoring
        rows: Indices of the rows from the original generator matrix
        that you want to use in the order that you want them
        '''
        n_rows = len(rows)
        n_cols = self.num_drives - 2
        mat = GenericMatrix((n_rows,n_cols),
                            mul=self.F.Multiply, div=self.F.Divide,
                            sub = self.F.Subtract, add=self.F.Add,
                            zeroElement=0, identityElement=1,
                            str=func)

        for i, row in enumerate(rows):
            mat.SetRow(i,self.gen_mat.GetRow(row))
            
#        print(mat)
        return mat
    
    def compute_parity(self,stripe):
        out = self.gen_mat.LeftMulColumnVec(stripe)
        return out
    
    
    def write_row(self,file):
        stripe = self.compute_parity(file)
        stripe_perm = roll(stripe,self.num_stripes)
        
        for i, drive in enumerate(self.drives):
            self.write_item(drive,stripe_perm[i],self.num_stripes)
            
        self.num_stripes += 1
        
    def add_file(self,file,file_id):
        #Pad to even number of rows
        full_stripes = int(len(file)/6)
        rem = len(file) - full_stripes*6
        if rem < 6 and rem > 0:
            for _ in range(6-rem):
                file.append(0)
        # Split into rows
        chunks = [file[x:x+6] for x in range(0, len(file), 6)]
        self.file_metadata.update({file_id:[len(chunks),rem,self.num_stripes]})
        for chunk in tqdm(chunks):
            self.write_row(chunk)
            
    def detect_format(self,file):
        if file.endswith('.png'):
            frm = '.png'
        elif file.endswith('txt'):
            frm = '.txt'
        else:
            raise ValueError('Invalid File Format!')
            return 0
        
        return frm
    
    def read_file_memory(self,file,frm):
        full_path = join(self.file_src,file)
        if frm == '.txt':
            with open(full_path,'r') as fp:

                x = fp.read()
                data = [int(el) for el in x.split()]
                
        elif frm == '.png':
            im = Image.open(full_path)
            data = array(im).flatten().tolist()
            
        return data
        
        
    def detect_new_file(self):
        files = os.listdir(self.file_src)
        if len(files) > len(self.files):
            print('New files detected!')
            for file in files:
                if file not in self.files:
                    print('Writing file: ',file)
                    data = self.read_file_memory(file,self.detect_format(file))
                    self.add_file(data,file)
                    self.files.append(file)
                    print('Done')
                
    def detect_failed_drives(self):
        available_drives = []
        self.failed_drives = False
        for drive in self.drives:
            if not os.path.exists(drive):
                print('Drive: ',drive,' does not exist')
                self.failed_drives = True
                available_drives.append(0)
            else:
                available_drives.append(1)
                if self.failed_drives:
                    self.available_drives = available_drives

        
    def assemble_stripe(self,idx,available_drives):
        stripe = zeros(sum(available_drives)).astype('uint8')
        index = 0
        for i, drive in enumerate(self.drives):
            if available_drives[i] == 1:
                stripe[index] = self.get_item(drive,idx)
                index += 1
        return stripe
    
    def stripe(self,i,rem_fixed,new_avail):
        stripe = self.assemble_stripe(i,rem_fixed)
        rem = roll(rem_fixed,-i)
        order = roll([0,1,2,3,4,5,6,7],i)
        rows_ordered = [el for el in order if el in np.argwhere(rem == 1)]
        igen_fail = self.build_error_generator_matrix(rows_ordered).Inverse()
        restored = self.restore_data(igen_fail,stripe)
        restored_stripe = self.compute_parity(restored)
        restored_stripe = roll(restored_stripe,i)
        # Write the restored stripe back to the replacement drive(s)
        for j, drive in enumerate(self.drives):
            if new_avail[j] == 0:
                self.write_item(drive,restored_stripe[j],i)
    
    def fix_failure(self):

        
        
        sleep(0.1)
        restored = False
        previous_avail = [1,1,1,1,1,1,1,1]
        

        self.detect_failed_drives()
        new_avail = [1 if p1 and p2 else 0 for p1,p2 in zip(previous_avail,self.available_drives)]
        rem_fixed = new_avail.copy()
        if sum(rem_fixed) > self.num_drives-2:
            idx = [i for i in range(len(rem_fixed)) if rem_fixed[i] == 1][0]
            rem_fixed[idx] = 0
        self.init_drives(drive=np.argwhere(array(new_avail) == 0).reshape(-1))

        
        t1 = time()
        arg1 = range(self.num_stripes)
        arg2 = iter([rem_fixed]*self.num_stripes)
        arg3 = iter([new_avail]*self.num_stripes)
        p = Pool(1)
        p.map(self.stripe,(arg1,arg2,arg3))
        t2 = time()
        print(t2-t1)
                




        
    def restore_data(self,igen_fail,stripe):

        restored_stripe = igen_fail.LeftMulColumnVec(stripe)
        return restored_stripe
    
    
    def write_item(self,drive,item,idx):
        full_rows = int(idx/self.drive_dim)
        rem = idx - full_rows*self.drive_dim
        D = np.load(drive,mmap_mode='r+')
        D[full_rows,rem] = item
        del D
#        self.drives[drive][full_rows,rem] = item
    
    
    def get_item(self,drive,stripe_idx):
        
        full_rows = int(stripe_idx/self.drive_dim)
        rem = int(stripe_idx - full_rows*self.drive_dim)
        D = np.load(drive,mmap_mode='r+')
        return D[full_rows,rem]
        
            
    def read_file(self,file_id):
        
        
        meta = self.file_metadata[file_id]
        start = meta[2]
        stop = start + meta[0]
        res_idx = 0
        
        stripes = []
        for j in range(start,stop):
            stripe = zeros(8).astype('uint8')
            for i, drive in enumerate(self.drives):
               stripe[i] = self.get_item(drive,j) 
               
               res_idx += 1
            stripe = roll(stripe,-j)
            stripes.append(stripe[0:-2])
        results = array(stripes).reshape(-1)
        if meta[1] > 0:
            garbage_bytes = 6 - meta[1]
            data = results[0:-garbage_bytes]
        else:
            data = results
        return data
        
        
drive_path = r'C:\Users\vijay\Documents\NTU\Distributed systems\Project2\drives'
file_src = r'C:\Users\vijay\Documents\NTU\Distributed systems\Project2\files'
cont = Raid6Controller(8,100000,drive_path,file_src)
cont.detect_new_file()
#
if __name__ == '__main__':
    __spec__ = "ModuleSpec(name='builtins', loader=<class '_frozen_importlib.BuiltinImporter'>)"

    while True:
        
        cont.detect_new_file()
        cont.detect_failed_drives()
        if cont.failed_drives:
            print('Failed drives')
            cont.fix_failure()
            print('Restored')
            cont.detect_failed_drives()
    #        break
    #        print(cont.drives)


#for key,_ in cont.file_metadata.items():
#    print(cont.read_file(key))
        
        