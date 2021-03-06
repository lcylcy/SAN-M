import numpy as np
import oneflow.experimental as flow
import oneflow.experimental.nn as nn
from model.fsmn import DFSMN_layer

class MultiHeadAttention(nn.Module):
    def __init__(self, n_head, d_model, d_k, d_v, dropout=0.1):
        super().__init__()

        self.n_head = n_head     
        self.d_k = d_k           
        self.d_v = d_v          

        self.w_qs = nn.Linear(d_model, n_head * d_k)   
        self.w_ks = nn.Linear(d_model, n_head * d_k) 
        self.w_vs = nn.Linear(d_model, n_head * d_v) 
        nn.init.normal_(self.w_qs.weight, mean=0, std=np.sqrt(2.0 / (d_model + d_k)))
        nn.init.normal_(self.w_ks.weight, mean=0, std=np.sqrt(2.0 / (d_model + d_k)))
        nn.init.normal_(self.w_vs.weight, mean=0, std=np.sqrt(2.0 / (d_model + d_v)))

        self.attention = ScaledDotProductAttention(temperature=np.power(d_k, 0.5),   
                                                   attn_dropout=dropout)             
        self.layer_norm = nn.LayerNorm(d_model)       

        self.fc = nn.Linear(n_head * d_v, d_model)    
        nn.init.xavier_normal_(self.fc.weight)

        self.dropout = nn.Dropout(dropout)

 
    def forward(self, q, k, v, mask=None):

        d_k, d_v, n_head = self.d_k, self.d_v, self.n_head 

        sz_b, len_q, _ = q.size()
        sz_b, len_k, _ = k.size()  
        sz_b, len_v, _ = v.size() 

        residual = q

        q = self.w_qs(q).reshape(shape =[sz_b, len_q, n_head, d_k]) 
        k = self.w_ks(k).reshape(shape=[sz_b, len_k, n_head, d_k]) 
        v = self.w_vs(v).reshape(shape=[sz_b, len_v, n_head, d_v]) 

        q = q.permute(2, 0, 1, 3).reshape(shape=[-1, len_q, d_k]) 
        k = k.permute(2, 0, 1, 3).reshape(shape=[-1, len_k, d_k]) 
        v = v.permute(2, 0, 1, 3).reshape(shape=[-1, len_v, d_v])

        if mask is not None:
            mask = mask.repeat(sizes = [n_head, 1, 1])

        output, attn = self.attention(q, k, v,mask)  

        output = output.reshape(shape=[n_head, sz_b, len_q, d_v])

        output = output.permute(1, 2, 0, 3).reshape(shape=[sz_b, len_q, -1])

        output = self.dropout(self.fc(output))
        output = self.layer_norm(output + residual)

        return output, attn


class ScaledDotProductAttention(nn.Module):
    def __init__(self, temperature, attn_dropout=0.1):
        super().__init__()
        self.temperature = temperature           
        self.dropout = nn.Dropout(attn_dropout) 
        self.softmax = nn.Softmax(dim=2)

    def forward(self, q, k, v, mask):

        attn = flow.matmul(q, k.transpose(1, 2))
        attn = attn / self.temperature

        if mask is not None:
            attn = attn.masked_fill(mask, -np.inf)

        attn = self.softmax(attn)
        attn = self.dropout(attn)
        output = flow.matmul(attn, v)

        return output, attn



class Sub_layer(nn.Module):
   
    def __init__(self, n_head, d_model, d_k, d_v, dropout=0.1,d_inner = 1280):
        super().__init__()

        self.n_head = n_head    
        self.d_k = d_k          
        self.d_v = d_v          
        self.w_qs = nn.Linear(d_model, n_head * d_k)   
        self.w_ks = nn.Linear(d_model, n_head * d_k)  
        self.w_vs = nn.Linear(d_model, n_head * d_v)   

        self.dfsmn = DFSMN_layer(n_head*d_v,n_head*d_v,d_inner,20,20,2,2)

        self.attention = ScaledDotProductAttention(temperature=np.power(d_k, 0.5),  
                                                   attn_dropout=dropout)             
        self.layer_norm = nn.LayerNorm(d_model)       


        self.dropout = nn.Dropout(dropout)


    def forward(self, q, k, v, mask=None,input_lengths=None):

        d_k, d_v, n_head = self.d_k, self.d_v, self.n_head  
     
        sz_b, len_q, _ = q.size()    
        sz_b, len_k, _ = k.size()   
        sz_b, len_v, _ = v.size()   

        residual = q

        q = self.w_qs(q).reshape(shape = [sz_b, len_q, n_head, d_k])  
        k = self.w_ks(k).reshape(shape = [sz_b, len_k, n_head, d_k]) 
        v = self.w_vs(v).reshape(shape = [sz_b, len_v, n_head, d_v])  

        v_out = v.reshape(shape = [sz_b,len_v,n_head*d_v])
        v_out = self.dfsmn(v_out,input_lengths)

        q = q.permute(2, 0, 1, 3).reshape(shape =[-1, len_q, d_k])  
        k = k.permute(2, 0, 1, 3).reshape(shape =[-1, len_k, d_k])  
        v = v.permute(2, 0, 1, 3).reshape(shape =[-1, len_v, d_v])  
        

        if mask is not None:
            mask = mask.repeat(sizes = (n_head, 1, 1))
        
        output, attn = self.attention(q, k, v, mask) 
        
        output = output.reshape(shape=[n_head, sz_b, len_q, d_v])

        output = output.permute(1, 2, 0, 3).reshape(shape = [sz_b, len_q, -1])

        output = output + v_out

        output = self.dropout(self.layer_norm(output + residual))

        return output, attn


__all__ = [ "MultiHeadAttention","sub_layer" ]

