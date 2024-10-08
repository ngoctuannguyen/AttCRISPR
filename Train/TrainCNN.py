import tensorflow as tf
from tensorflow.keras.layers import (
    Softmax, GlobalAveragePooling1D, Input, Conv2D, Flatten, 
    BatchNormalization, Multiply, Cropping1D, Dot, Bidirectional,
    LSTM, GRU, Dense, Dropout, Reshape, SpatialDropout1D, Lambda
)
from tensorflow.keras.layers import *
from tensorflow.keras.models import Model
from tensorflow.keras.callbacks import EarlyStopping, Callback, LambdaCallback
from tensorflow.keras.optimizers import Adam, RMSprop, SGD
import tensorflow.keras.backend as K
from hyperopt import fmin, tpe, hp, STATUS_OK, Trials
from LearnUtil import *
import math

def model(params):
    onehot_input = Input(name = 'onehot_input', shape = (21,4, 1,))
    conv_0 = Conv2D(30,(3,4),padding='same',activation='relu')(onehot_input)
    
    avgpooling_spatial = Lambda(lambda inp: K.mean(inp,axis=3,keepdims=True))(conv_0)
    maxpooling_spatial = Lambda(lambda inp: K.max(inp,axis=3,keepdims=True))(conv_0)
    attention_spatial = concatenate([maxpooling_spatial,avgpooling_spatial],axis=3)
    attention_spatial = BatchNormalization()(attention_spatial)
    attention_spatial = Conv2D(1, (3, 2), padding='same', activation='sigmoid',name='spatial_attention')(attention_spatial)
    conv_output = Lambda(lambda inp: inp[0]*inp[1],name='spatial_attention_result')( [onehot_input,attention_spatial])

    convs = []
    for i in range(params['cnn_conv_num']):
        convs.append(
            Conv2D(params['cnn_filters_num'],(i+2,4),strides=(1,4),padding='same',activation='relu')(conv_output)
            )
    conv_output = concatenate(convs,name='conv_output')
    pooling_output = conv_output
    cnn_output = Flatten()(pooling_output)

    onehot_embedded = mlp(cnn_output,output_layer_activation='tanh',output_dim=params['cnn_last_layer_units_num'],output_use_bias=False,
                          hidden_layer_num=params['cnn_fc_hidden_layer_num'],hidden_layer_units_num=params['cnn_fc_hidden_layer_units_num'],
                          hidden_layer_activation='relu',dropout=params['cnn_fc_dropout'],
                          name='cnn_embedding')
    output = Dense(units=1,kernel_regularizer='l2',name='spatial_score')(onehot_embedded)
    model = Model(inputs=[onehot_input],
                 outputs=[output],name='cnn')
    return model

def train(params,train_input,train_label,test_input,test_label,issave=True):
    result = Result()
    m = model(params)
    batch_size = params['train_batch_size'] #16
    learningrate = params['train_base_learning_rate'] # 0.00002
    epochs = params['train_epochs_num'] # 75
    m.compile(loss='mse', optimizer=Adam(learning_rate=learningrate))

    batch_end_callback = LambdaCallback(on_epoch_end=
                                        lambda batch,logs: 
                                        print(get_score_at_test(m,test_input,result,test_label,
                                                                issave=issave,savepath=params['cnn_save_file'])))

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
                                                              label['train'],rate=0,intensity=0)##### ??? noises
    train(params['CNNParams'],input_train_onehot,y_train,
          input['validate']['onehot'],label['validate'],
          input['test']['onehot'],label['test'])