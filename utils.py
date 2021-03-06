"""
Scipy version > 0.18 is needed, due to 'mode' option from scipy.misc.imread function
"""

import os
import h5py
import random

from PIL import Image  # for loading images as YCbCr format
import scipy.misc
import scipy.ndimage
import numpy as np

from skimage import transform,data

import tensorflow as tf


def read_data(path,is_train):
  """
  Read h5 format data file
  
  Args:
    path: file path of desired file
    data: '.h5' file format that contains train data values
    label: '.h5' file format that contains train label values
  """
  with h5py.File(path, 'r') as hf:
    data = np.array(hf.get('data'))
    if is_train:
      label = np.array(hf.get('label'))
      return data, label
    else:
      return data

def preprocess(path, is_train, scale):
  """
  Preprocess single image file 
    (1) Read original image as YCbCr format (and grayscale as default)
    (2) Normalize
    (3) Apply image file with bicubic interpolation

  Args:
    path: file path of desired file
    input_: image applied bicubic interpolation (low-resolution)
    label_: image with original resolution (high-resolution)
  """ 
  if is_train:
    image = imread(path, is_grayscale=False) 
    image = image[:,:,0] 
  
    # Must be normalized
    image = image / 255.

    label_ = modcrop(image, scale)
    input_ = scipy.ndimage.interpolation.zoom(label_, (1./scale), prefilter=False)
    input_ = scipy.ndimage.interpolation.zoom(input_, (scale/1.), prefilter=False)

    return input_, label_

  else:
    image = imread(path, is_grayscale=False)
    # Must be normalized

    h, w, _ = image.shape

    #no color change using this resize method
    image = transform.resize(image, (h//scale, w//scale, 3))
    image = transform.resize(image, (h, w, 3))

    input_dir = os.path.join(os.getcwd(),sample_dir,os.path.split(path)[-1])
    scipy.misc.imsave(input_dir, image)

    image = image / 255.

    return image

def is_image_file(filename):
    return any(filename.endswith(extension) for extension in [".bmp", ".png", ".jpg", ".jpeg"])

def prepare_data(sess, dataset):
  """
  Args:
    dataset: choose train dataset or test dataset
    
    For train dataset, output data would be ['.../t1.bmp', '.../t2.bmp', ..., '.../t99.bmp']
  """
  if is_train:
    data_dir = os.path.join(os.getcwd(), dataset)
    data = [os.path.join(data_dir, x) for x in os.listdir(data_dir) if is_image_file(x)]
  else:
    data_dir = os.path.join(os.getcwd(), dataset)
    data = [os.path.join(data_dir, x) for x in os.listdir(data_dir) if is_image_file(x)]

  return data

def make_data(sess, data, label=None):
  """
  Make input data as h5 file format
  Depending on 'is_train' (flag value), savepath would be changed.
  """
  if is_train:
    savepath = os.path.join(os.getcwd(), 'output/checkpoint/train.h5')
    with h5py.File(savepath, 'w') as hf:
      hf.create_dataset('data', data=data)
      hf.create_dataset('label', data=label) 

def imread(path, is_grayscale=True):
  """
  Read image using its path.
  Default value is gray-scale, and image is read by YCbCr format as the paper said.
  """
  if is_grayscale:
    return scipy.misc.imread(path, flatten=True, mode='YCbCr').astype(np.float)
  else:
    return scipy.misc.imread(path, mode='RGB').astype(np.float)

def modcrop(image, scale=3):
  """
  To scale down and up the original image, first thing to do is to have no remainder while scaling operation.
  
  We need to find modulo of height (and width) and scale factor.
  Then, subtract the modulo from height (and width) of original image size.
  There would be no remainder even after scaling operation.
  """
  if len(image.shape) == 3:
    h, w, _ = image.shape
    h = h - np.mod(h, scale)
    w = w - np.mod(w, scale)
    image = image[0:h, 0:w, :]
  else:
    h, w = image.shape
    h = h - np.mod(h, scale)
    w = w - np.mod(w, scale)
    image = image[0:h, 0:w]
  return image

def input_setup(sess, is_train,):
  """
  Read image files and make their sub-images and saved them as a h5 file format.
  """
  # Load data path
  if config.is_train:
    data = prepare_data(sess, dataset="dataset/Train")
  else:
    data = prepare_data(sess, dataset="dataset/Test")

  
  padding = abs(image_size - config.label_size) / 2 # 6

  if config.is_train:
    sub_input_sequence = []
    sub_label_sequence = []
    for i in range(len(data)):
      input_, label_ = preprocess(data[i], config)

      if len(input_.shape) == 3:
        h, w, _ = input_.shape
      else:
        h, w = input_.shape

      for x in range(0, h-config.image_size+1, config.stride):
        for y in range(0, w-config.image_size+1, config.stride):
          sub_input = input_[x:x+config.image_size, y:y+config.image_size] # [33 x 33]
          sub_label = label_[x+int(padding):x+int(padding)+config.label_size, y+int(padding):y+int(padding)+config.label_size] # [21 x 21]

          # Make channel value
          sub_input = sub_input.reshape([config.image_size, config.image_size, 1])  
          sub_label = sub_label.reshape([config.label_size, config.label_size, 1])

          sub_input_sequence.append(sub_input)
          sub_label_sequence.append(sub_label)

    arrdata = np.asarray(sub_input_sequence) # [?, 33, 33, 1]
    arrlabel = np.asarray(sub_label_sequence) # [?, 21, 21, 1]
    make_data(sess, arrdata, arrlabel)

  else:
    nx = np.zeros(len(data), dtype=np.int)
    ny = np.zeros(len(data), dtype=np.int)   
    arr = []

    for i in range(len(data)):
      image = preprocess(data[i], config)
      input_ = image
      sub_input_sequence = []             
      
      if len(input_.shape) == 3:
        h, w, _ = input_.shape
      else:
        h, w = input_.shape

      # Numbers of sub-images in height and width of image are needed to compute merge operation.
      for x in range(0, h-config.image_size+1, config.stride):
        nx[i] += 1; ny[i] = 0
        for y in range(0, w-config.image_size+1, config.stride):
          ny[i] += 1
          sub_input = input_[x:x+config.image_size, y:y+config.image_size, :] # [33 x 33]
          
          sub_input = sub_input.reshape([config.image_size, config.image_size, 3])  
          
          sub_input_sequence.append(sub_input)

      arr.append(np.asarray(sub_input_sequence))
      sub_input_sequence.clear()
  """
  len(sub_input_sequence) : the number of sub_input (33 x 33 x ch) in one image
  (sub_input_sequence[0]).shape : (33, 33, 1)
  """
  if not config.is_train:
    return nx, ny, np.asarray(arr)


def imsave(image, path):
  image = image * 255.
  return scipy.misc.imsave(path, image)

def merge(images, size):
  h, w = images.shape[1], images.shape[2]
  img = np.zeros((h*size[0], w*size[1], 1))
  for idx, image in enumerate(images):
    i = idx % size[1]
    j = idx // size[1]
    img[j*h:j*h+h, i*w:i*w+w, :] = image

  return img
