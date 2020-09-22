import ParamsUtil
from ParamsUtil import *
######

from TrainRNN import train as RNN
from TrainCNN import train as CNN
from Ensemble import train as Ensemble

def Pipeline(pretrainCNN=False,pretrainRNN=False,ensemble=False,fineTuning=False):
    data = Read_Data()
    input = data['input']
    label = data['label']
    r = None
    if pretrainCNN:
        input_train_onehot,input_train_biofeat,y_train = AddNoise(input['train']['onehot'],input['train']['biofeat'],
                                                                  label['train'],rate=0,intensity=0)
        r = CNN(params['CNNParams'],input_train_onehot,y_train,
             input['validate']['onehot'],label['validate'],
             input['test']['onehot'],label['test'])
    if pretrainRNN:
        input_train_onehot,input_train_biofeat,y_train = AddNoise(input['train']['onehot'],input['train']['biofeat'],
                                                                  label['train'],rate=0,intensity=0)
        r = RNN(params['RNNParams'],input_train_onehot,y_train,
             input['validate']['onehot'],label['validate'],
             input['test']['onehot'],label['test'])
    if ensemble:
        #input_train_onehot,input_train_biofeat,y_train = AddNoise(input['train']['onehot'],input['train']['biofeat'],
        #                                                          label['train'],rate=50,intensity=10)
        input_train_onehot,input_train_biofeat,y_train = input['train']['onehot'],input['train']['biofeat'],label['train']
        r = Ensemble(params['EnsembleParams'],
                 input_train_onehot,input_train_biofeat,y_train,
                 input['validate']['onehot'],input['validate']['biofeat'],label['validate'],
                 input['test']['onehot'],input['test']['biofeat'],label['test'],
                 cnn_trainable=False,rnn_trainable=False)
    if fineTuning:
        r = Ensemble(params['FineTuning'],
                input['train']['onehot'],input['train']['biofeat'],label['train'],
                input['validate']['onehot'],input['validate']['biofeat'],label['validate'],
                input['test']['onehot'],input['test']['biofeat'],label['test'],
                cnn_trainable=True,rnn_trainable=True,load_weight=True)
    return r
if __name__ == "__main__":
    Pipeline(pretrainCNN=False,pretrainRNN=False,ensemble=False,fineTuning=True) 