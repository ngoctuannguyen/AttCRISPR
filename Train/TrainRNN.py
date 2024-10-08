import tensorflow as tf
# from tensorflow.keras.layers import (
#     Softmax, GlobalAveragePooling1D, Input, Conv2D, Flatten, 
#     BatchNormalization, Multiply, Cropping1D, Dot, Bidirectional,
#     LSTM, GRU, Dense, Dropout, Reshape, SpatialDropout1D, Lambda
# )
from tensorflow.keras.layers import *
from tensorflow.keras.models import Model
from tensorflow.keras.callbacks import EarlyStopping, Callback, LambdaCallback
from tensorflow.keras.optimizers import Adam, RMSprop, SGD
import tensorflow.keras.backend as K
from hyperopt import fmin, tpe, hp, STATUS_OK, Trials
from LearnUtil import *
import math
import numpy as np


def GaussianKernelBuffer(windowsize):
    gaussian = lambda d: math.exp( -(d*d)*2/windowsize/windowsize ) if abs(d)<=windowsize/2 else 0
    result = []
    for i in range(21):
        resultat = []
        for j in range(21):
            resultat.append(gaussian(i-j))
        nresultat = np.array(resultat)
        result.append(nresultat)
    #magic
    for i in range(21):
        sum=0
        for j in range(21):
            sum+=result[i][j]
        time=21/sum
        for j in range(21):
            result[i][j]*=time
    return np.array(result)
def model(params):
    GaussianBuffer = GaussianKernelBuffer(params['rnn_window_size'])
    onehot_input = Input(name = 'onehot_input', shape = (21,4, 1,))
    embedded = Conv2D(params['rnn_embedding_output'], (1, 4),strides=(1,4), padding='Valid', activation=None)(onehot_input) 
    # -> [10, 110]
    embedded = Reshape((21,params['rnn_embedding_output'],))(embedded)
    # -> [21, 10, 110]
    embedded = SpatialDropout1D(0.25)(embedded)
    
    ######encoder&decoder######
    encoder = GRU(params['rnn_unit_num'],return_sequences=True,return_state=True,unroll=True)
    encoder = Bidirectional(encoder,merge_mode='sum',name='encoder')
    encoder_output,ec1,ec2 = encoder(embedded)

    decoder_input = embedded
    decoder = GRU(params['rnn_unit_num'],return_sequences=True,return_state=True,unroll=True,
                  kernel_regularizer=tf.keras.regularizers.l2(0.01),
                  recurrent_regularizer=tf.keras.regularizers.l2(0.01),dropout=0.25,recurrent_dropout=0.25)
    decoder = Bidirectional(decoder,merge_mode='sum',name='decoder')
    if params['rnn_use_context_state']:
        decoder_output,dc1,dc2 = decoder(decoder_input,initial_state=[ec1,ec2])  
    else:
        decoder_output,dc1,dc2 = decoder(decoder_input)
    encoderat = []
    decoderat = []
    for i in range(21):
        encoderat.append(
            Flatten()(Cropping1D(cropping=(i,21-1-i))(encoder_output)))
        decoderat.append(
            Flatten()(Cropping1D(cropping=(i,21-1-i))(decoder_output)))
    ######attention######
    aat = []
    sqrtd = math.sqrt(params['rnn_unit_num'])
    for i in range(21):
        atat = []
        for j in range(21):
            #importance of pos[j] in scoring pos[i]
            align = dot([encoderat[j],decoderat[i]],axes=-1)
            atat.append(
                align
                )
        ## add l2 regular
        at = concatenate(atat)
        at = BatchNormalization()(at)
        #l2(0.00001) is opt while 0.001 is best
        at = Dense(21,activation='softmax',use_bias=True,activity_regularizer=keras.regularizers.l2(0.00001))(at)
        #at[j] importance of pos[j] in scoring pos[i]

        at = Reshape((1,21,))(at)
        aat.append(at)
    #aat[i][j] importance of pos[j] in scoring pos[i]
    m = concatenate(aat,axis=-2)
    weight = Lambda(lambda inp: K.constant(GaussianBuffer)*inp ,name = 'temporal_attention')(m)
    weightavg = Lambda(lambda inp: K.batch_dot(inp[0],inp[1]),name='weight_avg')([weight,encoder_output])
    
    scoreat = []
    for i in range(21):
        tat = Flatten()(Cropping1D(cropping=(i,21-1-i))(weightavg))
        edat = Flatten()(Cropping1D(cropping=(i,21-1-i))(embedded))
        tat = Dense(params['rnn_embedding_output'],activation='tanh',use_bias=False)(tat)
        scoreat.append(
            dot([tat,edat],axes=-1)
            )
    score = concatenate(scoreat)
    
    rnn_embedded = score
    #magic
    rnn_embedded = Dropout(rate=params['rnn_last_dropout'])(rnn_embedded)
    output = Dense(units=1,kernel_regularizer=tf.keras.regularizers.l2(0.001),kernel_constraint=tf.keras.constraints.NonNeg(),
                   name='temporal_score',activation=params['rnn_last_activation'],
                   use_bias=params['rnn_last_use_bias'])(rnn_embedded)
    model = Model(inputs=[onehot_input],
                 outputs=[output],name='rnn')
    return model

def train(params,train_input,train_label,test_input,test_label,issave=True):
    result = Result()
    m = model(params)
    batch_size = params['train_batch_size']
    learningrate = params['train_base_learning_rate']
    epochs = params['train_epochs_num']
    optimizer = params['optimizer']
    m.compile(loss='mse', optimizer=optimizer(learning_rate=learningrate))

    batch_end_callback = LambdaCallback(on_epoch_end=
                                        lambda batch,logs: 
                                        print(get_score_at_test(m,test_input,result,test_label,
                                                                issave=issave,savepath=params['rnn_save_file'])))

    m.fit(train_input,train_label,
          batch_size=batch_size,
          epochs=epochs,
          verbose=2,
          validation_split=0.1, 
          callbacks=[batch_end_callback])
    return {'loss': -1*result.Best, 'status': STATUS_OK}
if __name__ == "__main__":
    import ParamsUtil
    from ParamsUtil import *
    dataset = 'WT'
    data = ReadData(dataset)
    params = GetParams(dataset)
    input = data['input']
    label = data['label']
    input_train_onehot,input_train_biofeat,y_train = AddNoise(input['train']['onehot'],input['train']['biofeat'],
                                                              label['train'],rate=0,intensity=0)
    params['RNNParams']['rnn_embedding_output'] = 150
    params['RNNParams']['rnn_unit_num'] = 100
    scores = []
    for i in range(3,4):
        thisbest = train(params['RNNParams'],input_train_onehot,y_train,
                    input['validate']['onehot'],label['validate'],
                    input['test']['onehot'],label['test'])['loss']
        scores.append(thisbest)
        print(scores)