#!/usr/bin/env python
# -*- coding: utf-8 -*-

from keras import layers
from keras import models
from keras.layers.convolutional import UpSampling2D, Conv2D
from keras.layers.pooling import AveragePooling2D, MaxPooling2D
from keras.layers.normalization import BatchNormalization
from keras.layers.core import Dropout, Activation

#
# network params
#

cardinality = 32


def residual_network(x):
    """
    ResNeXt by default. For ResNet set `cardinality` = 1 above.

    """

    def add_common_layers(y):
        y = layers.BatchNormalization()(y)
        y = layers.LeakyReLU()(y)

        return y

    def grouped_convolution(y, nb_channels, _strides):
        # when `cardinality` == 1 this is just a standard convolution
        if cardinality == 1:
            return layers.Conv2D(nb_channels, kernel_size=(3, 3), strides=_strides, padding='same')(y)

        assert not nb_channels % cardinality
        _d = nb_channels // cardinality

        # in a grouped convolution layer, input and output channels are divided into `cardinality` groups,
        # and convolutions are separately performed within each group
        groups = []
        for j in range(cardinality):
            group = layers.Lambda(lambda z: z[:, :, :, j * _d:j * _d + _d])(y)
            groups.append(layers.Conv2D(_d, kernel_size=(3, 3), strides=_strides, padding='same')(group))

        # the grouped convolutional layer concatenates them as the outputs of the layer
        y = layers.concatenate(groups)

        return y

    def residual_block(y, nb_channels_in, nb_channels_out, _strides=(1, 1), _project_shortcut=False):
        """
        Our network consists of a stack of residual blocks. These blocks have the same topology,
        and are subject to two simple rules:
        - If producing spatial maps of the same size, the blocks share the same hyper-parameters (width and filter sizes).
        - Each time the spatial map is down-sampled by a factor of 2, the width of the blocks is multiplied by a factor of 2.
        """
        shortcut = y

        # we modify the residual building block as a bottleneck design to make the network more economical
        y = layers.Conv2D(nb_channels_in, kernel_size=(1, 1), strides=(1, 1), padding='same')(y)
        y = add_common_layers(y)

        # ResNeXt (identical to ResNet when `cardinality` == 1)
        y = grouped_convolution(y, nb_channels_in, _strides=_strides)
        y = add_common_layers(y)

        y = layers.Conv2D(nb_channels_out, kernel_size=(1, 1), strides=(1, 1), padding='same')(y)
        # batch normalization is employed after aggregating the transformations and before adding to the shortcut
        y = layers.BatchNormalization()(y)

        # identity shortcuts used directly when the input and output are of the same dimensions
        if _project_shortcut or _strides != (1, 1):
            # when the dimensions increase projection shortcut is used to match dimensions (done by 1×1 convolutions)
            # when the shortcuts go across feature maps of two sizes, they are performed with a stride of 2
            shortcut = layers.Conv2D(nb_channels_out, kernel_size=(1, 1), strides=_strides, padding='same')(shortcut)
            shortcut = layers.BatchNormalization()(shortcut)

        y = layers.add([shortcut, y])

        # relu is performed right after each batch normalization,
        # expect for the output of the block where relu is performed after the adding to the shortcut
        y = layers.LeakyReLU()(y)

        return y

    # conv1
    x = layers.Conv2D(64, kernel_size=(7, 7), strides=(2, 2), padding='same')(x)
    x = add_common_layers(x)

    # conv2
    x = layers.MaxPool2D(pool_size=(3, 3), strides=(2, 2), padding='same')(x)
    for i in range(3):
        project_shortcut = True if i == 0 else False
        x = residual_block(x, 128, 256, _project_shortcut=project_shortcut)

    # conv3
    for i in range(1):
        # down-sampling is performed by conv3_1, conv4_1, and conv5_1 with a stride of 2
        strides = (2, 2) if i == 0 else (1, 1)
        x = residual_block(x, 256, 512, _strides=strides)

    # conv4
    for i in range(1):
        strides = (2, 2) if i == 0 else (1, 1)
        x = residual_block(x, 512, 1024, _strides=strides)

    # conv5
    for i in range(1):
        strides = (2, 2) if i == 0 else (1, 1)
        x = residual_block(x, 1024, 2048, _strides=strides)

    #x = layers.GlobalAveragePooling2D()(x)
    #x = layers.Dense(1)(x)

    # UpSampling
    up0 = UpSampling2D(size=(2,2))(x)
    conv_up0 = Conv2D(96, (3, 3), padding="same", kernel_initializer="normal", name = "conv_up0")(up0)
    bn_up0 = BatchNormalization(name = "bn_up0")(conv_up0)
    ac_up0 = Activation('relu', name='ac_up0')(bn_up0)

    up1 = UpSampling2D(size=(2,2))(ac_up0)
    conv_up1 = Conv2D(64, (3, 3), padding="same", kernel_initializer="normal", name = "conv_up1")(up1)
    bn_up1 = BatchNormalization(name = "bn_up1")(conv_up1)
    ac_up1 = Activation('relu', name='ac_up1')(bn_up1)

    up2 = UpSampling2D(size=(2,2))(ac_up1)
    conv_up2 = Conv2D(32, (3, 3), padding="same", kernel_initializer="normal", name = "conv_up2")(up2)
    bn_up2 = BatchNormalization(name = "bn_up2")(conv_up2)
    ac_up2 = Activation('relu', name='ac_up2')(bn_up2)

    up3 = UpSampling2D(size=(2,2))(ac_up2)
    conv_up3 = Conv2D(32, (3, 3), padding="same", kernel_initializer="normal", name = "conv_up3")(up3)
    bn_up3 = BatchNormalization(name = "bn_up3")(conv_up3)
    ac_up3 = Activation('relu', name='ac_up3')(bn_up3)

    up4 = UpSampling2D(size=(2, 2))(ac_up3)
    conv_up4 = Conv2D(16, (3, 3), padding="same", kernel_initializer="normal", name="conv_up4")(up4)
    conv_up4 = Dropout(rate=0.3)(conv_up4)
    bn_up4 = BatchNormalization(name="bn_up4")(conv_up4)
    ac_up4 = Activation('relu', name='ac_up4')(bn_up4)

    x = Conv2D(3, (1,1), padding="same", kernel_initializer="normal", name="dense167classifer")(ac_up4)

    return x

