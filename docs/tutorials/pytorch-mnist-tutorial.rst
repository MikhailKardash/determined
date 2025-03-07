.. _pytorch-mnist-tutorial:

########################
 PyTorch MNIST Tutorial
########################

.. meta::
   :description: Using a simple image classification model for the MNIST dataset, you'll Learn how to port an existing PyTorch model to Determined.
   :keywords: PyTorch API,MNIST,model developer,quickstart

In this tutorial, you'll learn how to port an existing PyTorch model to Determined. We will port a
simple image classification model for the MNIST dataset. This tutorial is based on the official
`PyTorch MNIST example <https://github.com/PyTorch/examples/blob/master/mnist/main.py>`_.

*********************
 About Model Porting
*********************

To use a PyTorch model in Determined, you need to port the model to Determined's API. For most
models, this porting process is straightforward, and once the model has been ported, all of the
features of Determined will then be available. For example, you can perform :ref:`distributed
training <multi-gpu-training>` and :ref:`hyperparameter search <hyperparameter-tuning>` without
changing your model code. Determined will store and visualize your model metrics automatically.

When training a PyTorch model, Determined provides a built-in training loop that feeds each batch of
training data into your ``train_batch`` function, which should perform the forward pass,
backpropagation, and compute training metrics for the batch. Determined also handles checkpointing,
log management, and device initialization. To plug your model code into the Determined training
loop, you define methods to perform the following tasks:

-  Initialize the models, optimizers, and LR schedulers.
-  Define the training function for forward and backward passes.
-  Define the evaluation function to compute the loss and other metrics on the validation data set.
-  Load the training data set.
-  Load the validation data set.

The Determined training loop will then invoke these functions automatically. These methods should be
organized into a **trial class**, which is a user-defined Python class that inherits from
:class:`determined.pytorch.PyTorchTrial`. The following sections walk through how to write your
first trial class and then how to run a training job with Determined.

***************
 Prerequisites
***************

-  Access to a Determined cluster. If you have not yet installed Determined, refer to the
   :ref:`installation instructions <installation-guide>`.

-  Access to the Determined CLI on your local machine. See :ref:`the installation instructions
   <install-cli>` if you do not already have it installed. After installing the CLI, configure it to
   connect to your Determined cluster by setting the ``DET_MASTER`` environment variable to the
   hostname or IP address where Determined is running.

.. note::

   For basic instructions on how to start a Determined cluster locally and run an experiment using
   the ``mnist_pytorch`` example, visit :ref:`Run Your First Experiment in Determined
   <pytorch_mnist_quickstart>`.

****************************
 Getting the Tutorial Files
****************************

-  Download the complete code for this tutorial from :download:`mnist_pytorch.tgz
   </examples/mnist_pytorch.tgz>`.
-  After downloading the file, open a terminal window, extract the file, and ``cd`` into the
   ``mnist_pytorch`` directory:

.. code::

   tar xzvf mnist_pytorch.tgz
   cd mnist_pytorch

-  Follow along with the code as you complete the tutorial.

*************************************
 Creating the ``PyTorchTrial`` Class
*************************************

Outlined below is a basic structure for our trial class:

.. code:: python

   import torch.nn as nn
   from determined.pytorch import DataLoader, PyTorchTrial, PyTorchTrialContext


   class MNISTTrial(PyTorchTrial):
       def __init__(self, context: PyTorchTrialContext):
           # Initialize the trial class and wrap the models, optimizers, and LR schedulers.
           pass

       def train_batch(self, batch: TorchData, epoch_idx: int, batch_idx: int):
           # Run forward passes on the models and backward passes on the optimizers.
           pass

       def evaluate_batch(self, batch: TorchData):
           # Define how to evaluate the model by calculating loss and other metrics
           # for a batch of validation data.
           pass

       def build_training_data_loader(self):
           # Create the training data loader.
           # This should return a determined.pytorch.Dataset.
           pass

       def build_validation_data_loader(self):
           # Create the validation data loader.
           # This should return a determined.pytorch.Dataset.
           pass

Let's dive deeper into the implementation of each of these methods.

Initialization
==============

As with any Python class, the ``__init__`` method is invoked to construct our trial class.
Determined passes this method a single parameter, an instance of
:class:`~determined.pytorch.PyTorchTrialContext`, which inherits from
:class:`~determined.TrialContext`. The trial context contains information about the trial, such as
the values of the hyperparameters to use for training. All the models and optimizers must be wrapped
with ``wrap_model`` and ``wrap_optimizer`` respectively, which are provided by
:class:`~determined.pytorch.PyTorchTrialContext`. In this MNIST example, the model code uses the
Torch Sequential API and ``torch.optim.Adadelta``. The current values of the model's hyperparameters
can be accessed via the :func:`~determined.TrialContext.get_hparam` method of the trial context.

.. code:: python

   def __init__(self, context: PyTorchTrialContext):
       # Store trial context for later use.
       self.context = context

       # Create a unique download directory for each rank so they don't overwrite each
       # other when doing distributed training.
       self.download_directory = f"/tmp/data-rank{self.context.distributed.get_rank()}"
       self.data_downloaded = False

       # Initialize the model and wrap it using self.context.wrap_model().
       self.model = self.context.wrap_model(
           nn.Sequential(
               nn.Conv2d(1, self.context.get_hparam("n_filters1"), 3, 1),
               nn.ReLU(),
               nn.Conv2d(
                   self.context.get_hparam("n_filters1"),
                   self.context.get_hparam("n_filters2"),
                   3,
               ),
               nn.ReLU(),
               nn.MaxPool2d(2),
               nn.Dropout2d(self.context.get_hparam("dropout1")),
               Flatten(),
               nn.Linear(144 * self.context.get_hparam("n_filters2"), 128),
               nn.ReLU(),
               nn.Dropout2d(self.context.get_hparam("dropout2")),
               nn.Linear(128, 10),
               nn.LogSoftmax(),
           )
       )

       # Initialize the optimizer and wrap it using self.context.wrap_optimizer().
       self.optimizer = self.context.wrap_optimizer(
           torch.optim.Adadelta(
               model.parameters(), lr=self.context.get_hparam("learning_rate")
           )
       )

Load Data
=========

The next two methods we need to define are ``build_training_data_loader`` and
``build_validation_data_loader``. Determined uses these methods to load the training and validation
datasets, respectively. Both methods should return a :ref:`determined.pytorch.DataLoader
<pytorch-data-loading>`, which is very similar to ``torch.utils.data.DataLoader``.

.. code:: python

   def build_training_data_loader(self):
       if not self.data_downloaded:
           self.download_directory = data.download_dataset(
               download_directory=self.download_directory,
               data_config=self.context.get_data_config(),
           )
           self.data_downloaded = True

       train_data = data.get_dataset(self.download_directory, train=True)
       return DataLoader(train_data, batch_size=self.context.get_per_slot_batch_size())


   def build_validation_data_loader(self):
       if not self.data_downloaded:
           self.download_directory = data.download_dataset(
               download_directory=self.download_directory,
               data_config=self.context.get_data_config(),
           )
           self.data_downloaded = True

       validation_data = data.get_dataset(self.download_directory, train=False)
       return DataLoader(
           validation_data, batch_size=self.context.get_per_slot_batch_size()
       )

Define ``train_batch``
======================

The :func:`~determined.pytorch.PyTorchTrial.train_batch` method is passed a single batch of data
from the training data set; it should run the forward passes on the models, the backward passes on
the losses, and step the optimizers. This method should return a dictionary with user-defined
training metrics; Determined will automatically average all the metrics across batches. If an
optimizer is set to automatically handle zeroing out the gradients, ``step_optimizer`` will zero out
the gradients and there will be no need to call ``optim.zero_grad()``.

.. code:: python

   def train_batch(self, batch: TorchData, epoch_idx: int, batch_idx: int):
       batch = cast(Tuple[torch.Tensor, torch.Tensor], batch)
       data, labels = batch

       # Define the training forward pass and calculate loss.
       output = self.model(data)
       loss = torch.nn.functional.nll_loss(output, labels)

       # Define the training backward pass and step the optimizer.
       self.context.backward(loss)
       self.context.step_optimizer(self.optimizer)

       return {"loss": loss}

Define ``evaluate_batch``
=========================

The :func:`~determined.pytorch.PyTorchTrial.evaluate_batch` method is passed a single batch of data
from the validation data set; it should compute the user-defined validation metrics on that data,
and return them as a dictionary that maps metric names to values. The metric values for each batch
are reduced (aggregated) to produce a single value of each metric for the entire validation set. By
default, metric values are averaged but this behavior can be customized by overridding
:func:`~determined.pytorch.PyTorchTrial.evaluation_reducer`.

.. code:: python

   def evaluate_batch(self, batch: TorchData):
       batch = cast(Tuple[torch.Tensor, torch.Tensor], batch)
       data, labels = batch

       output = self.model(data)
       validation_loss = torch.nn.functional.nll_loss(output, labels).item()

       pred = output.argmax(dim=1, keepdim=True)
       accuracy = pred.eq(labels.view_as(pred)).sum().item() / len(data)

       return {"validation_loss": validation_loss, "accuracy": accuracy}

*****************
 Train the Model
*****************

Now that we have ported our model code to the trial API, we can use Determined to train a single
instance of the model or to do a hyperparameter search. In Determined, a trial is a training task
that consists of a dataset, a deep learning model, and values for all of the model's
hyperparameters. An experiment is a collection of one or more trials: an experiment can either train
a single model (with a single trial), or can define a search over a user-defined hyperparameter
space.

To create an experiment, we start by writing a configuration file that defines the kind of
experiment we want to run. In this case, we want to train a single model for a single epoch, using
fixed values for the model's hyperparameters:

.. code:: yaml

   name: mnist_pytorch_const
   data:
     url: https://s3-us-west-2.amazonaws.com/determined-ai-test-data/pytorch_mnist.tar.gz
   hyperparameters:
     learning_rate: 1.0
     global_batch_size: 64
     n_filters1: 32
     n_filters2: 64
     dropout1: 0.25
     dropout2: 0.5
   records_per_epoch: 50_000
   searcher:
     name: single
     metric: validation_loss
     max_length:
       epochs: 1
     smaller_is_better: true
   entrypoint: model_def:MNistTrial

The ``entrypoint`` specifies the name of the trial class to use. This is useful if the model code
contains more than one trial class. In this case, we use an entrypoint of ``model_def:MNistTrial``
because our trial class is named ``MNistTrial`` and it is defined in a Python file named
``model_def.py``.

For more information on experiment configuration, see the :ref:`experiment configuration reference
<experiment-configuration>`.

*******************
 Run an Experiment
*******************

:ref:`The Determined CLI <cli-ug>` can be used to create a new experiment, which will immediately
start running on the cluster. To do this, we run:

.. code::

   det experiment create const.yaml .

Here, the first argument (``const.yaml``) is the name of the experiment configuration file and the
second argument (``.``) is the location of the directory that contains our model definition files.
You may need to configure the CLI with the network address where the Determined master is running,
via the ``-m`` flag or the ``DET_MASTER`` environment variable.

Once the experiment is started, you will see a notification:

.. code::

   Preparing files (.../mnist_pytorch) to send to master... 2.5KB and 4 files
   Created experiment xxx

********************
 Evaluate the Model
********************

Model evaluation is done automatically for you by Determined. To access information on both training
and validation performance, simply go to the WebUI by entering the address of the Determined master
in your web browser.

Once you are on the Determined landing page, you can find your experiment using the experiment's ID
(``xxx`` in the example above) or description.

************
 Next Steps
************

Now that you are familiar with porting model code to Determined, you can keep working with the
PyTorch MNIST model and learn how to :ref:`get up and running with the Core API <api-core-ug>`.
