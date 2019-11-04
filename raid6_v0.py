from pyfinite.ffield import FField
from pyfinite.genericmatrix import GenericMatrix
from numpy import array, zeros, append, empty, asarray, roll
import numpy as np


class Raid6Controller():
    ''' Basic Raid6 Controller. This version can handle 
    files that are consist of 4 bytes, represented as 4 uint8 values
    in 0 to 255. '''
    
    def __init__(self,num_drives,drive_cap):
        self.num_drives = num_drives
        self.drive_cap = drive_cap
        self.F = FField(8)
        self.num_stripes = 0
        self.gen_mat = self.build_generator_matrix()
        self.drives = zeros((drive_cap,num_drives)).astype('uint8')
        self.parity_placement_counter = 0
        self.file_id = 0
        self.failed_drives = None
        
    def build_generator_matrix(self):
        rows = self.num_drives
        cols = self.num_drives - 2
        mat = GenericMatrix(size=(rows,cols),
                            mul=self.F.Multiply, div=self.F.Divide,
                            sub = self.F.Subtract, add=self.F.Add,
                            zeroElement=0, identityElement=1)
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
                            zeroElement=0, identityElement=1)

        for i, row in enumerate(rows):
            mat.SetRow(i,self.gen_mat.GetRow(row))
            
#        print(mat)
        return mat
    
    def compute_parity(self,stripe):
        out = self.gen_mat.LeftMulColumnVec(stripe)
        return out
    
    def permute_stripe(self,stripe,idx):  
        ''' Permute a stripe by rolling.
        This is for distributing the parities across drives
        '''
        stripe_perm = roll(stripe,idx)
        return stripe_perm
    
    
    def add_file(self,file):
        stripe = self.compute_parity(file)
        stripe_perm = self.permute_stripe(stripe,self.file_id)

        self.drives[self.file_id,:] = stripe_perm
        self.file_id += 1
        
    def fail_drives(self,failed_drives):
        self.drives = np.delete(self.drives,failed_drives,axis=1)
        self.failed_drives = failed_drives
        
    def detect_failed_drives(self):
        if self.drives.shape[1] < self.num_drives:
            self.fix_failure()
            
    def fix_failure(self):
        new_drives = zeros((self.drive_cap,self.num_drives)).astype('uint8')
        rem_list = [1 if i not in self.failed_drives else 0 for i in range(self.num_drives)]
        for i in range(self.drives.shape[0]):
            stripe = self.drives[i,:]
            rem = np.roll(rem_list,-i)
            order = np.roll([0,1,2,3,4,5,6,7],i)
            rows_ordered = [el for el in order if el in np.argwhere(rem==1)]
            igen_fail = self.build_error_generator_matrix(rows_ordered).Inverse()
            restored = self.restore_data(igen_fail,stripe)
            restored_stripe = self.compute_parity(restored)
            restored_stripe = self.permute_stripe(restored_stripe,i)
            new_drives[i,:] = restored_stripe
#            print(restored)
            
        self.drives = new_drives
        
        
    def restore_data(self,igen_fail,stripe):

        restored_stripe = igen_fail.LeftMulColumnVec(stripe)
        return restored_stripe
    
    def read_file(self,file_id):
        stripe = self.drives[file_id,:]
        stripe_unperm = np.roll(stripe,-file_id)
        data = stripe_unperm[0:-2]
        return data
        
        
    
cont = Raid6Controller(8,6)
files = []
# Create random "files" consisting of 6 1-byte symbols
# and write them to disks
print('Original random files:\n')
for i in range(6): #Create 6 files
    file = [np.random.randint(0,255) for _ in range(6)]
#    print(file)
    cont.add_file(file)
    files.append(file)
    print(file)
print('\n'
      )
#Read files from disks
print('Files read from disks after striping:\n')
for i in range(6):
    print(cont.read_file(i))
print('\n')

print('Break 2 disks, detect failure, and reconstruct')
# Break 2 disks:
cont.fail_drives([0,1])
# Detech failure and reconstruct
cont.detect_failed_drives()

print('Reconstructed files read from disks:\n')
# Read reconstructed files:
for i in range(6):
    print(cont.read_file(i))







        
        