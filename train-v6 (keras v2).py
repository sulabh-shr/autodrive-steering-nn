import csv
import cv2
import numpy as np
import time

from matplotlib import pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.utils import shuffle

from keras.models import Sequential
from keras.layers import Flatten, Dense, Lambda, Cropping2D, Dropout
from keras.layers.convolutional import Conv2D
from keras.layers.pooling import MaxPooling2D
from keras.layers.advanced_activations import LeakyReLU
from keras.optimizers import Adam

from keras.callbacks import ModelCheckpoint, EarlyStopping


def load_csv_file(path_to_csv):
    """
        FUNCTION TO LOAD THE CSV FILE
            iterating through the elements (lines) of csv reader
            appending to the list: lines
            returning the list of lines
    """
    print('\nLOADING CSV LINES..............')

    lines = []
    with open(path_to_csv) as csv_file:
        reader = csv.reader(csv_file)
        for line in reader:
            lines.append(line)

    print('CSV LOADED')
    print('Total lines in CSV: ', len(lines))

    return lines            #  1st line in csv file may be header


def generator(csv_lines, path_to_img, batch_size=50, correction=0.2):
    """
    :param csv_lines:
    :param path_to_img:
    :param batch_size:
    :param correction:
    :return: yield x_train, y_train

    Generator that uses passed csv_lines to read images and
    it's augmented images i.e. mirror and left/right images
    and their respective steering angle as labels.
    Correction is used to add/subtract from center image steering angle
    when using left/right images.
    Hence, yields a batch of batch size = passed batch_size*6
    """

    num_lines = len(csv_lines)
    print('\nGENERATING DATA \nNo. of data: {}'.format(num_lines*6))

    while 1:
        shuffle(csv_lines)
        print('\nSHUFFLING DATA.................')
        """
            SPLITTING CSV_LINES INTO BATCHES
                taking a part of csv_lines of size batch_size
                storing the batch in batch_lines
                    iterating over lines in the batch_lines
                        adding 3 data in images, measurements per line
        """
        print('Number of data in batch: {}\n'.format(batch_size*6))
        for offset in range(0, num_lines, batch_size):
            batch_lines = csv_lines[offset:offset + batch_size]
            images = []  # List to store images
            measurements = []  # List to store corresponding steering measurement

            for line in batch_lines:
                """
                    STEERING DATA ARRAY
                        Making a steering measurement data array
                        1st element is the center steering
                        2nd element is the left steering
                        3rd element is the right steering
                """
                steering = []
                steering_center = float(line[3])
                steering.append(steering_center)
                steering.append(steering_center + correction)  # steering_left
                steering.append(steering_center - correction)  # steering_right

                for i in range(3):  # iterating through center, left, right
                    source_path = line[i]
                    filename = source_path.split('/')[-1]
                    current_path = path_to_img + filename
                    image = cv2.imread(current_path)
                    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)    # cv2 reads in BGR but simulator in RGB
                    images.append(image)
                    measurements.append(steering[i])
                    """
                        AUGMENTING DATA
                            Flipping the image
                            Reversing the measurement data
                    """
                    images.append(np.fliplr(image))
                    measurements.append((-1.0) * steering[i])
            x_train = np.array(images)
            y_train = np.array(measurements)
            assert len(x_train) == len(y_train), 'Error!!! Length of x not equal to y'
            # print('\nNumber of data in batch: {}\n'.format(len(x_train)))
            yield shuffle(x_train, y_train)


def my_model():
    model = Sequential()
    model.add(Cropping2D(cropping=((70, 25), (0, 0)), input_shape=(160, 320, 3)))
    #   cropping top 70 pixels and bottom 25 pixels and 0 left and 0 right pixels
    model.add(Lambda(lambda x: x / 255.0 - 0.5))
    #   dividing by max and subtracting by 0.5 to normalize around 0 --> [-.5,.5]

    model.add(Conv2D(filters=20, kernel_size=(3, 3), padding='valid', strides=(2, 2)))
    model.add(LeakyReLU(alpha=0.3))
    model.add(MaxPooling2D(pool_size=(2, 2), padding='same'))
    model.add(Dropout(0.1))

    model.add(Conv2D(filters=40, kernel_size=(1, 1), padding='same', strides=(1, 1)))
    model.add(LeakyReLU(alpha=0.3))
    model.add(MaxPooling2D(pool_size=(2, 2), padding='same'))
    model.add(Dropout(0.1))

    model.add(Conv2D(filters=60, kernel_size=(3, 3), padding='same', strides=(1, 1)))
    model.add(LeakyReLU(alpha=0.3))
    model.add(MaxPooling2D(pool_size=(2, 2), padding='same'))
    model.add(Dropout(0.1))

    model.add(Conv2D(filters=120, kernel_size=(1, 1), padding='same', strides=(1, 1)))
    model.add(LeakyReLU(alpha=0.3))
    model.add(Dropout(0.1))

    model.add(Conv2D(filters=200, kernel_size=(3, 3)))
    model.add(LeakyReLU(alpha=0.3))

    model.add(Flatten())
    model.add(Dropout(0.1))
    model.add(Dense(100))
    model.add(Dropout(0.4))
    model.add(Dense(40))
    model.add(Dropout(0.75))
    model.add(Dense(10))
    model.add(Dense(1))

    return model


def main(path_to_csv, path_to_img, no_of_epoch=2, batch_size=32, correction=0.3, learning_rate=0.001):
    print('EXECUTING MAIN FUNCTION\n')
    # line(row) from csv file containing image names, steering angle and various params
    lines_from_csv = load_csv_file(path_to_csv)
    # Splitting lines into train and validation sets
    train_lines, validation_lines = train_test_split(lines_from_csv, test_size=0.2)
    train_generator = generator(train_lines, path_to_img, batch_size, correction)
    validation_generator = generator(validation_lines, path_to_img, batch_size, correction)

    model = my_model()
    print(model.summary())

    adam = Adam(lr=learning_rate)               # can change learning rate here
    model.compile(loss='mean_squared_error', optimizer=adam)

    check_save_name = 'cp: epoch - {epoch:02d}, v_loss - {val_loss:.4f}.h5'
    checkpoint = ModelCheckpoint(check_save_name, save_best_only=True, period=0)
    early_stop = EarlyStopping(monitor='val_loss', min_delta=0, patience=7, verbose=1)
    history_object = model.fit_generator(train_generator,
                                         steps_per_epoch=(len(train_lines)/batch_size),
                                         validation_data=validation_generator,
                                         validation_steps=(len(validation_lines)/batch_size),
                                         epochs=no_of_epoch, callbacks=[checkpoint, early_stop],
                                         use_multiprocessing=False, workers=1)
    '''
        STEPS PER EPOCH
            The steps per epoch is equal to total number of unique data divided by batch size
            i.e. [ len(sample_lines)*6 ] / [ batch_size*6 ]
            because each batch produces 6 times the data
            so, net result remains the omission of 6 in both numerator and denominator
    '''

    save_name = 'model- {}--{}-{}.h5'.format(time.ctime(), no_of_epoch, batch_size)
    model.save(save_name)

    try:
        # print the keys obtained
        print(history_object.history.keys())

        # plot the training and validation loss
        plt.plot(history_object.history['loss'])
        plt.plot(history_object.history['val_loss'])
        plt.title('Model mean squared error loss')
        plt.ylabel('mean squared error loss')
        plt.xlabel('epoch')
        plt.legend(['training set', 'validation set'], loc='upper right')
        plt.show()
    except Exception as e:
        print('ERROR WHILE LOSS VISUALIZATION ', e)


if __name__ == '__main__':
    print('INITIALIZING MAIN METHOD...................')

    """
        VARIOUS PARAMETERS
            parameters that can be changed
    """
    csv_path = 'my_data/driving_log.csv'
    img_path = 'my_data/IMG/'
    batch = 150
    epoch = 100
    correct = 0.2
    learning = 0.001
    start = time.time()

    main(csv_path, img_path, epoch, batch, correct, learning)
    print('\n\nElapsed time: ', time.time() - start)
