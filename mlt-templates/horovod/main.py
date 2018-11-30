#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2018 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: EPL-2.0
#

"""
Runs simple convolutional model to train MNIST
"""
import os
from datetime import datetime

import tensorflow as tf
from tensorflow import layers
from tensorflow.examples.tutorials.mnist import input_data

FLAGS = tf.app.flags.FLAGS
tf.app.flags.DEFINE_integer("num_inter_threads", 2,
                            "# inter op threads")

tf.app.flags.DEFINE_integer("num_threads", os.cpu_count(),
                            "# intra op threads")

tf.app.flags.DEFINE_integer("total_steps", 4000,
                            "Number of training steps")

tf.app.flags.DEFINE_integer("log_steps", 20,
                            "Number of steps between logs")

tf.app.flags.DEFINE_integer("batch_size", 128,
                            "Batch Size for Training")

tf.app.flags.DEFINE_string("data_path",
                           '',
                           "Data directory")

tf.app.flags.DEFINE_string("output_path", '',
                           "Output log directory")

tf.app.flags.DEFINE_boolean("no_horovod", False,
                            "Don't use Horovod. Single node training only.")

tf.app.flags.DEFINE_float("learning_rate", 0.001,
                          "Learning rate")

tf.app.flags.DEFINE_string("s3_endpoint", '',
                           "Endpoint for S3 storage, blank means no S3")

tf.app.flags.DEFINE_string("aws_region", 'Local',
                           "Region for AWS S3")

tf.app.flags.DEFINE_string("s3_use_https", '1',
                           "HTTPS is used to access S3 by default")

tf.app.flags.DEFINE_string("s3_verify_ssl", '1',
                           "HTTPS is used for S3 by default")

tf.app.flags.DEFINE_string("aws_access_key_id", '',
                           "S3 storage credentials")

tf.app.flags.DEFINE_string("aws_secret_access_key", '',
                           "S3 storage credentials")

config = tf.ConfigProto(intra_op_parallelism_threads=FLAGS.num_threads,
                        inter_op_parallelism_threads=FLAGS.num_inter_threads)

tf.logging.set_verbosity(tf.logging.INFO)

if FLAGS.s3_endpoint:
    # Set S3 Environment Variables
    os.environ["S3_ENDPOINT"] = FLAGS.s3_endpoint
    os.environ["S3_VERIFY_SSL"] = FLAGS.s3_verify_ssl
    os.environ["S3_USE_HTTPS"] = FLAGS.s3_use_https
    os.environ["AWS_ACCESS_KEY_ID"] = FLAGS.aws_access_key_id
    os.environ["AWS_SECRET_ACCESS_KEY"] = FLAGS.aws_secret_access_key
    os.environ["AWS_REGION"] = FLAGS.aws_region

if not FLAGS.no_horovod:
    import horovod.tensorflow as hvd


def get_model(feature, label):
    # Reshape the input vector into a 28x28 image
    input_layer = tf.reshape(feature, [-1, 28, 28, 1])

    conv1 = tf.layers.conv2d(
        inputs=input_layer,
        filters=32,
        kernel_size=[5, 5],
        padding="same",
        activation=tf.nn.relu,
        name="conv1")

    pool1 = tf.layers.max_pooling2d(
        inputs=conv1,
        pool_size=[2, 2],
        strides=2,
        name="pool1")

    conv2 = tf.layers.conv2d(
        inputs=pool1,
        filters=64,
        kernel_size=[5, 5],
        padding="same",
        activation=tf.nn.relu,
        name="conv2")

    pool2 = tf.layers.max_pooling2d(
        inputs=conv2,
        pool_size=[2, 2],
        strides=2,
        name="pool2")

    # Flatten
    pool2_flat = layers.Flatten()(pool2)

    # Add a Dense layer
    dense = tf.layers.dense(inputs=pool2_flat,
                            units=1024,
                            activation=tf.nn.relu,
                            name="Dense1")

    # Add a dropout layer
    dropout = tf.layers.dropout(
        inputs=dense,
        rate=0.4,  # Dropout rate
        training=True,
        name="dropout")

    # Logits Layer
    logits = tf.layers.dense(inputs=dropout,
                             units=10,
                             name="Logits_layer")

    onehot_labels = tf.one_hot(tf.cast(label, tf.int32), 10, 1, 0)

    loss = tf.losses.softmax_cross_entropy(onehot_labels=onehot_labels,
                                           logits=logits)

    correct_prediction = tf.equal(tf.cast(tf.argmax(logits, 1),
                                          tf.float32), label)
    accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

    """
    Print out TensorBoard Summaries
    """
    tf.summary.scalar("loss", loss)
    tf.summary.histogram("loss", loss)
    tf.summary.scalar("training_accuracy", accuracy)
    tf.summary.image("images", input_layer, max_outputs=3)
    # summary_op = tf.summary.merge_all()

    return tf.argmax(logits, 1), loss, accuracy


def main(_):
    start_time = datetime.now()
    tf.logging.info("Starting at: {}".format(start_time))
    tf.logging.info("Batch size: {} images per step".format(FLAGS.batch_size))

    if not FLAGS.no_horovod:
        # Initialize Horovod.
        hvd.init()

    # Download MNIST dataset.
    mnist = input_data.read_data_sets(FLAGS.data_path, one_hot=False)

    # Input tensors
    with tf.name_scope("input"):
        image = tf.placeholder(tf.float32, [None, 784], name="image")
        label = tf.placeholder(tf.float32, [None], name="label")

    # Define model
    predict, loss, accuracy = get_model(image, label)

    if not FLAGS.no_horovod:
        # Horovod: adjust learning rate based on number workers
        opt = tf.train.RMSPropOptimizer(FLAGS.learning_rate * hvd.size())
    else:
        opt = tf.train.RMSPropOptimizer(FLAGS.learning_rate)

    # Wrap optimizer with Horovod Distributed Optimizer.
    if FLAGS.no_horovod is None:
        opt = hvd.DistributedOptimizer(opt)

    global_step = tf.train.get_or_create_global_step()
    train_op = opt.minimize(loss, global_step=global_step)

    if not FLAGS.no_horovod:
        last_step = FLAGS.total_steps // hvd.size()
    else:
        last_step = FLAGS.total_steps

    def formatter_log(tensors):
        if FLAGS.no_horovod:
            logstring = "Step {} of {}: " \
                        " training loss = {:.4f}," \
                        " training accuracy = {:.4f}".\
                        format(tensors["step"], last_step,
                               tensors["loss"], tensors["accuracy"])
        else:
            logstring = "HOROVOD (Worker #{}), Step {} of {}: " \
                        " training loss = {:.4f}," \
                        " training accuracy = {:.4f}".\
                format(hvd.rank(),
                       tensors["step"],
                       last_step,
                       tensors["loss"],
                       tensors["accuracy"])

        return logstring

    hooks = [

        tf.train.StopAtStepHook(last_step=last_step),

        # Prints the loss and step every log_steps steps
        tf.train.LoggingTensorHook(tensors={"step": global_step,
                                            "loss": loss,
                                            "accuracy": accuracy},
                                   every_n_iter=FLAGS.log_steps,
                                   formatter=formatter_log),
    ]

    # Horovod: BroadcastGlobalVariablesHook broadcasts
    # initial variable states from rank 0 to all other
    # processes. This is necessary to ensure consistent
    # initialization of all workers when training is
    # started with random weights
    # or restored from a checkpoint.
    if not FLAGS.no_horovod:
        hooks.append(hvd.BroadcastGlobalVariablesHook(0))

        # Horovod: save checkpoints only on
        # worker 0 to prevent other workers from
        # corrupting them.
        if hvd.rank() == 0:
            checkpoint_dir = "{}/{}-workers/{}".\
                format(FLAGS.output_path,
                       hvd.size(),
                       datetime.now().strftime("%Y%m%d-%H%M%S"))
        else:
            checkpoint_dir = None

    else:
        checkpoint_dir = "{}/no_hvd/{}".\
            format(FLAGS.output_path,
                   datetime.now().strftime("%Y%m%d-%H%M%S"))

    # The MonitoredTrainingSession takes care of session initialization,
    # restoring from a checkpoint, saving to a checkpoint,
    # and closing when done or an error occurs.
    with tf.train.\
            MonitoredTrainingSession(checkpoint_dir=checkpoint_dir,
                                     hooks=hooks,
                                     save_summaries_steps=FLAGS.log_steps,
                                     log_step_count_steps=FLAGS.log_steps,
                                     config=config) as mon_sess:
        while not mon_sess.should_stop():
            # Run a training step synchronously.
            image_, label_ = mnist.train.next_batch(FLAGS.batch_size)
            mon_sess.run(train_op, feed_dict={image: image_, label: label_})

    stop_time = datetime.now()
    tf.logging.info("Stopping at: {}".format(stop_time))
    tf.logging.info("Elapsed time was: {}".format(stop_time - start_time))


if __name__ == "__main__":
    tf.app.run()
