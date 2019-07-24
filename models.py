import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt


# def MLP(x, hidden_layer_sizes, output_size, var_scope):
#   with tf.variable_scope(var_scope, reuse=tf.AUTO_REUSE):
#     for i, hidden_layer_size in enumerate(hidden_layer_sizes):
#       x = tf.keras.layers.Dense(name='hidden_{}'.format(i), units=hidden_layer_size, activation=tf.nn.relu)(x)
#     if output_size == 1:
#       logits = tf.squeeze(tf.keras.layers.Dense(name='output', units=1)(x))
#     else:
#       logits = tf.keras.layers.Dense(name='output', units=output_size)(x)
#     return logits

class MNISTMLP:
  def __init__(self, hidden_layer_sizes, output_size, var_scope):
    self.hidden_layer_sizes = hidden_layer_sizes
    self.output_size = output_size
    self.var_scope = var_scope

  def forward(self, x):
    with tf.variable_scope(self.var_scope, reuse=tf.AUTO_REUSE):
      for i, hidden_layer_size in enumerate(self.hidden_layer_sizes):
        x = tf.layers.dense(inputs=x, name='hidden_{}'.format(i), units=hidden_layer_size, activation=tf.nn.relu)

      logits = tf.layers.dense(inputs=x, name='output', units=self.output_size)
      if self.output_size == 1:
          logits = tf.squeeze(logits)

      return logits

class MNISTConvNet:
  def __init__(self, output_size, var_scope):
    self.output_size = output_size
    self.var_scope = var_scope

  def forward(self, x):
    x = tf.reshape(x, [-1, 28, 28, 1])
    with tf.variable_scope(self.var_scope, reuse=tf.AUTO_REUSE):
      # https://github.com/MadryLab/mnist_challenge/blob/master/model.py
      x = tf.layers.conv2d(inputs=x, filters=32, kernel_size=(5, 5), activation='relu', padding='same')
      x = tf.nn.max_pool(x, ksize = [1,2,2,1], strides=[1,2,2,1], padding='SAME')
      # x = tf.layers.max_pooling2d(inputs=x, pool_size=(2, 2))
      x = tf.layers.conv2d(inputs=x, filters=64, kernel_size=(5, 5), activation='relu', padding='same')
      # x = tf.layers.max_pooling2d(inputs=x, pool_size=(2, 2))
      x = tf.nn.max_pool(x, ksize = [1,2,2,1], strides=[1,2,2,1], padding='SAME')

      x = tf.reshape(x, [-1, 7 * 7 * 64])
      x = tf.layers.dense(inputs=x, units=1024, activation='relu')
      logits = tf.layers.dense(inputs=x, units=self.output_size)

      if self.output_size == 1:
          logits = tf.squeeze(logits)

      return logits

class Detector(object):
  def __init__(self, var_scope, mode=None, dataset='MNIST'):
    self.output_size = 1
    self.var_scope = var_scope

    self.y_input = tf.placeholder(tf.int64, shape=[None])

    if dataset == 'MNIST':
      self.input_size = 28*28*1
      self.x_input = tf.placeholder(tf.float32, shape=[None, self.input_size])
      self.net = MNISTConvNet(output_size=1, var_scope=var_scope)
      self.logits = self.net.forward(self.x_input)

    self.y_xent = tf.nn.sigmoid_cross_entropy_with_logits(labels=tf.cast(self.y_input, tf.float32),
                                                         logits=self.logits)

    self.xent = tf.reduce_mean(self.y_xent)

    self.predictions = tf.cast(self.logits > 0, tf.int64)

    correct_prediction = tf.equal(self.predictions, self.y_input)

    self.num_correct = tf.reduce_sum(tf.cast(correct_prediction, tf.int64))
    self.accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

    true_positives = tf.bitwise.bitwise_and(self.y_input, self.predictions)
    self.true_positive_rate = tf.reduce_sum(true_positives) / tf.reduce_sum(self.y_input)

    false_positives = tf.bitwise.bitwise_and(1 - self.y_input, self.predictions)
    self.false_positive_rate = tf.reduce_sum(false_positives) / tf.reduce_sum(1 - self.y_input)

    self.recall = self.true_positive_rate
    self.precision = tf.reduce_sum(true_positives) / tf.reduce_sum(self.predictions)

    self.f_score = 2 * (self.precision * self.recall) / (self.precision + self.recall)

    # TODO validate formulation
    self.balanced_accuracy = 0.5 * (self.true_positive_rate + (1.0 - self.false_positive_rate))

    # self.x_input_nat = tf.boolean_mask(self.x_input, tf.equal(self.y_input, 0))
    # self.x_input_adv = tf.boolean_mask(self.x_input, tf.equal(self.y_input, 1))


class Classifier(object):
  def __init__(self, var_scope, mode=None, dataset='MNIST'):
    self.var_scope = var_scope
    self.y_input = tf.placeholder(tf.int64, shape=[None])
    self.output_size = 10

    assert dataset in ['MNIST', 'CIFAR10']
    if dataset == 'MNIST':
      self.input_size = 28 * 28 * 1
      self.x_input = tf.placeholder(tf.float32, shape=[None, self.input_size])
      self.net = MNISTConvNet(output_size=self.output_size, var_scope=var_scope)
      self.logits = self.net.forward(self.x_input)

    self.y_xent = tf.nn.sparse_softmax_cross_entropy_with_logits(
      labels=self.y_input, logits=self.logits)

    self.xent = tf.reduce_mean(self.y_xent)

    self.predictions = tf.argmax(self.logits, 1)

    correct_prediction = tf.equal(self.predictions, self.y_input)

    self.num_correct = tf.reduce_sum(tf.cast(correct_prediction, tf.int64))
    self.accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))


class PGDAttack:
  def __init__(self, max_distance, num_steps, step_size, random_start,
               x_min, x_max, batch_size, norm, optimizer):
    """Attack parameter initialization. The attack performs k steps of
       size a, while always staying within epsilon from the initial
       point."""
    self.max_distance = max_distance
    self.num_steps = num_steps
    self.step_size = step_size
    self.rand = random_start
    self.x_min = x_min
    self.x_max = x_max
    self.norm = norm
    self.optimizer = optimizer

    input_size = 28*28
    self.delta = tf.Variable(np.zeros((batch_size, input_size)), dtype=tf.float32, name='delta')
    self.x0 = tf.Variable(np.zeros((batch_size, input_size)), dtype=tf.float32, name='x0')
    self.y = tf.Variable(np.zeros(batch_size), dtype=tf.int64, name='y')
    
    self.delta_input = tf.placeholder(dtype=tf.float32, shape=[batch_size, input_size], name='delta_input')
    self.x0_input = tf.placeholder(dtype=tf.float32, shape=[batch_size, input_size], name='x0_input')
    self.y_input = tf.placeholder(dtype=tf.int64, shape=[batch_size], name='delta_input')
    
    self.assign_delta = self.delta.assign(self.delta_input)
    self.assign_x0 = self.x0.assign(self.x0_input)
    self.assign_y = self.y.assign(self.y_input)

    self.x = self.x0 + self.delta
    ord = {'L2': 2, 'Linf': np.inf}[norm]
    self.dist = tf.norm(self.x - self.x0, ord=ord, axis=1)

  def setup_optimizer(self):
    if self.optimizer == 'adam':
      # Setup the adam optimizer and keep track of variables we're creating
      start_vars = set(x.name for x in tf.global_variables())
      optimizer = tf.train.AdamOptimizer(learning_rate=self.step_size, name='attack_adam')
      self.train_step = optimizer.minimize(self.loss, var_list=[self.delta])
      end_vars = tf.global_variables()
      new_vars = [x for x in end_vars if x.name not in start_vars]
      self.init = tf.variables_initializer(new_vars)
    elif self.optimizer == 'normgrad':
      if self.norm == 'Linf':
        self.train_step = self.delta.assign(self.delta + self.step_size * tf.sign(tf.gradients(-self.loss, self.delta)[0]))
      else:
        grad = tf.gradients(-self.loss, self.delta)[0]
        grad_norm = tf.norm(grad, axis=1, keepdims=True)
        grad_norm = tf.clip_by_value(grad_norm, np.finfo(float).eps, np.inf)
        self.train_step = self.delta.assign(self.delta + self.step_size * grad / grad_norm)

    with tf.control_dependencies([self.train_step]):
      # following https://adversarial-ml-tutorial.org/adversarial_examples/
      delta_ = tf.minimum(tf.maximum(self.delta, self.x_min - self.x0), self.x_max - self.x0)
      if self.norm == 'L2':
        norm = tf.norm(delta_, axis=1, keepdims=True)
        # TODO use np.inf instead of tf.reduce_max(norm)
        # delta_ = delta_ * self.max_distance / tf.clip_by_value(norm, clip_value_min=self.max_distance,
        #                                                        clip_value_max=tf.reduce_max(norm))
        bound_norm = tf.clip_by_value(norm, clip_value_min=np.finfo(float).eps, clip_value_max=self.max_distance)
        delta_ = delta_ * bound_norm / tf.clip_by_value(norm, clip_value_min=np.finfo(float).eps, clip_value_max=np.inf)
      else:
        delta_ = tf.clip_by_value(delta_, -self.max_distance, self.max_distance)
      self.calibrate_delta = self.delta.assign(delta_)

  def perturb(self, x_nat, y, sess, verbose=False, ax=None):
    delta = np.zeros_like(x_nat)
    if self.rand and not ax:
      if self.norm == 'L2':
        delta = np.random.randn(*x_nat.shape)
        scale = np.random.uniform(low=0.0, high=self.max_distance, size=[delta.shape[0], 1])
        delta = scale * delta / np.linalg.norm(delta, axis=1, keepdims=True)
      else:
        delta = np.random.uniform(-self.max_distance, self.max_distance, x_nat.shape)
      # delta = np.minimum(np.maximum(delta, self.x_min - x_nat), self.x_max - x_nat)

    if self.optimizer == 'adam':
      sess.run(self.init)

    if y is None:
      sess.run([self.assign_delta, self.assign_x0], feed_dict={
        self.delta_input: delta, self.x0_input: x_nat})
    else:
      sess.run([self.assign_delta, self.assign_x0, self.assign_y], feed_dict={
        self.delta_input: delta, self.x0_input: x_nat, self.y_input: y})

    if verbose:
      plt.figure(figsize=(10, 10))
      print(self.norm, self.max_distance)
    prev_dist = np.zeros(delta.shape[0])
    for i in range(self.num_steps):
      if verbose:
        delta, dist, logits, x = sess.run([self.delta, self.dist, self.detector_logits, self.x])
        print('step {}'.format(i), end=': ')
        #print('max {}'.format(np.round(np.max(x, axis=1), 4)[:5]), end=' | ')
        #print('dist update {}'.format(np.round(np.absolute(dist - prev_dist), 4)[:5]), end=' | ')
        print('dist {}'.format(np.round(dist, 4)[:5]), end=' | ')
        print('logit {}'.format(np.round(logits, 3)[:5]))
        prev_dist = dist
        #  if i % 99 == 0:
        #    #M = N = int(np.sqrt(x.shape[0]))
        #    M = N = 10
        #    dim = 28
        #    pad = 1
        #    space = dim + pad
        #    tiling = np.ones((space * M, space * N), dtype=np.float32)
        #    for m in range(M):
        #      for n in range(N):
        #        tiling[m*space: m*space+dim, n*space: n*space+dim] = x[m*M+n].reshape((28, 28))
        #    plt.imshow(tiling, cmap='gray')
        #    plt.axis('off')
        #    plt.title('step {}'.format(i))
        #    # plt.show()
        #    plt.savefig('painting/img{:04d}.png'.format(i//1), bbox_inches='tight')
        # # haven't saturated but already stopped increasing
        #mask = np.logical_and(dist < self.max_distance - 0.1, np.absolute(dist - prev_dist) < 0.01)
        #delta[mask] = delta[mask] + np.random.uniform(-0.02, 0.02, delta[mask].shape)
        #sess.run(self.assign_delta, feed_dict={self.delta_input: delta})
      sess.run([self.train_step, self.calibrate_delta])
      if ax:
        x = sess.run(self.x)
        ax.plot(x[0, 0], x[0, 1], 'rx')

    return sess.run(self.x)

  def madry_perturb(self, x_nat, y, sess, verbose=False):
    delta = np.zeros_like(x_nat)
    if self.rand:
      if self.norm == 'L2':
        delta = np.random.randn(*x_nat.shape)
        scale = np.random.uniform(low=0.0, high=self.max_distance, size=[delta.shape[0], 1])
        delta = scale * delta / np.linalg.norm(delta, axis=1, keepdims=True)
      else:
        delta = np.random.uniform(-self.max_distance, self.max_distance, x_nat.shape)
      # delta = np.minimum(np.maximum(delta, self.x_min - x_nat), self.x_max - x_nat)

    if self.optimizer == 'adam':
      sess.run(self.init)
    sess.run([self.assign_x0, self.assign_delta, self.assign_y], feed_dict={self.y_input: y, self.x0_input: x_nat, self.delta_input: delta})

    for i in range(self.num_steps):
      grad = sess.run(self.classifier_grad)

      if self.norm == 'L2':
        delta += self.step_size * grad / np.linalg.norm(grad, axis=1)
        delta = np.minimum(np.maximum(delta, self.x_min - x_nat), self.x_max - x_nat)
        delta_norm = np.linalg.norm(delta, axis=1, keepdims=True)
        delta = delta * self.max_distance / np.clip(delta_norm, a_min=self.max_distance, a_max=None)
      else:
        delta += self.step_size * np.sign(grad)
        delta = np.minimum(np.maximum(delta, self.x_min - x_nat), self.x_max - x_nat)
        delta = np.clip(delta, -self.max_distance, self.max_distance)

      sess.run(self.assign_delta, feed_dict={self.delta_input: delta})

    return sess.run([self.x, self.dist, self.classifier_logits])


class PGDAttackDetector(PGDAttack):
  def __init__(self, detector, **kwargs):
    super().__init__(**kwargs)
    self.detector_logits = detector.net.forward(self.x)
    # self.detector_logits = detector.forward(self.x)
    if kwargs['optimizer'] == 'normgrad':
      labels = tf.zeros_like(self.detector_logits)
      self.loss = -tf.reduce_sum(
        tf.nn.sigmoid_cross_entropy_with_logits(labels=labels, logits=self.detector_logits))
    else:
      self.loss = tf.reduce_sum(-self.detector_logits)
    self.setup_optimizer()


class PGDAttackClassifier(PGDAttack):
  def __init__(self, classifier, loss_fn, **kwargs):
    super().__init__(**kwargs)
    if loss_fn == 'xent':
      logits = classifier.forward(self.x)
      y_xent = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=self.y, logits=logits)
      self.loss = -tf.reduce_sum(y_xent)
      if isinstance(classifier, BayesianOVR):
          raise ValueError('BayesianOVR not supported')
    elif loss_fn == 'cw':
      logits = classifier.forward(self.x)
      label_mask = tf.one_hot(self.y, classifier.output_size, dtype=tf.float32)
      correct_logit = tf.reduce_sum(label_mask * logits, axis=1)
      wrong_logit = tf.reduce_max((1 - label_mask) * logits - 1e4 * label_mask, axis=1)
      if isinstance(classifier, BayesianOVR):
        self.loss = tf.reduce_sum(-wrong_logit)
      else:
        self.loss = tf.reduce_sum(correct_logit - wrong_logit)
    self.setup_optimizer()


class PGDAttackBayesianOVR(PGDAttack):
  def __init__(self, classifier, loss_fn, **kwargs):
    super().__init__(**kwargs)
    if loss_fn == 'xent':
      # self.loss = -tf.reduce_sum(classifier.y_xent)
      logits = classifier.forward(self.x)
      y_xent = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=self.y, logits=logits)
      self.loss = -tf.reduce_sum(y_xent)
      #self.loss = -y_xent
    elif loss_fn == 'cw':
      # logits = classifier.net.forward(self.x)
      logits = classifier.forward(self.x)
      label_mask = tf.one_hot(self.y, classifier.output_size, dtype=tf.float32)
      correct_logit = tf.reduce_sum(label_mask * logits, axis=1)
      wrong_logit = tf.reduce_max((1 - label_mask) * logits - 1e4 * label_mask, axis=1)
      #self.loss = tf.reduce_sum(correct_logit - wrong_logit)
      self.loss = tf.reduce_sum(- wrong_logit)
    self.setup_optimizer()

class PGDAttackAda(PGDAttack):
  def __init__(self, target, classifier, detector, method, **kwargs):
    super().__init__(**kwargs)
    clf_logits = classifier.net.forward(self.x)
    det_logits = detector.net.forward(self.x)

    targets = tf.fill(tf.shape(self.x)[0:1], target)
    target_mask = tf.one_hot(targets, 10, dtype=tf.float32)
    correct_logit = tf.reduce_max(clf_logits - 1e4 * target_mask, axis=1)
    wrong_logit = clf_logits[:, target]

    if method == 'cw':
      with_det_logits = (-det_logits + 1) * tf.reduce_max(clf_logits, axis=1)
      correct_logit_with_det = tf.maximum(correct_logit, with_det_logits)
      self.loss = tf.reduce_sum(correct_logit_with_det - wrong_logit)
    else:
      mask = tf.cast(tf.greater(wrong_logit, correct_logit), tf.float32)
      self.loss = tf.reduce_sum(mask * (-det_logits) + (1.0 - mask) * (correct_logit - wrong_logit))

    self.setup_optimizer()




'''
class PGDAttackBayesianOVR(PGDAttack):
  def __init__(self, detectors, thresholds=np.zeros(10), **kwargs):
    super().__init__(**kwargs)
    ovr_logits = [d.net.forward(self.x) - t for d, t in zip(detectors, thresholds)]
    ovr_logits = tf.stack(ovr_logits, axis=1)
    det_logits = -tf.reduce_max(ovr_logits, axis=1, keepdims=True)
    with_det_logits = tf.concat([ovr_logits, det_logits], axis=1)
    self.predictions = tf.argmax(with_det_logits, 1)

    label_mask = tf.one_hot(self.y, 10, dtype=tf.float32)
    wrong_logit = tf.reduce_max((1 - label_mask) * ovr_logits - 1e4 * label_mask, axis=1)

    self.loss = tf.reduce_sum(-wrong_logit)

    self.setup_optimizer()
'''

class BayesianOVR(object):
  def __init__(self, detectors):
    self.y_input = tf.placeholder(tf.int64, shape=[None])
    self.output_size = 10
    self.detectors = detectors

    self.input_size = 28 * 28 * 1
    self.x_input = tf.placeholder(tf.float32, shape=[None, self.input_size])

    self.logits = self.forward(self.x_input)

    self.y_xent = tf.nn.sparse_softmax_cross_entropy_with_logits(
      labels=self.y_input, logits=self.logits)

    self.xent = tf.reduce_mean(self.y_xent)

    self.predictions = tf.argmax(self.logits, 1)

    correct_prediction = tf.equal(self.predictions, self.y_input)

    self.num_correct = tf.reduce_sum(tf.cast(correct_prediction, tf.int64))
    self.accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))
  
  def forward(self, x):
    # shape: [batch, num_classes]
    return tf.stack([d.net.forward(x) for d in self.detectors], axis=1)

class MadryLinfPGDAttackDetector:
  def __init__(self, detector, epsilon, num_steps, step_size, random_start, x_min, x_max):
    """Attack parameter initialization. The attack performs k steps of
       size a, while always staying within epsilon from the initial
       point."""
    self.detector = detector
    self.epsilon = epsilon
    self.num_steps = num_steps
    self.step_size = step_size
    self.rand = random_start
    self.x_min = x_min
    self.x_max = x_max

    # https://github.com/MadryLab/mnist_challenge/blob/master/model.py#L48
    # https://github.com/MadryLab/mnist_challenge/blob/master/pgd_attack.py#L38
    loss = tf.reduce_sum(detector.y_xent)
    self.grad = tf.gradients(loss, detector.x_input)[0]

  def perturb(self, x_nat, sess):
    """Given a set of examples (x_nat, y), returns a set of adversarial
       examples within epsilon of x_nat in l_infinity norm."""
    if self.rand:
      x = x_nat + np.random.uniform(-self.epsilon, self.epsilon, x_nat.shape)
      #x = np.clip(x, self.x_min, self.x_max) # ensure valid pixel range
    else:
      x = np.copy(x_nat)
    y = np.zeros(x.shape[0], dtype=np.int64)

    for i in range(self.num_steps):
      grad = sess.run(self.grad, feed_dict={self.detector.x_input: x, self.detector.y_input: y})

      x = np.add(x, self.step_size * np.sign(grad), out=x, casting='unsafe')

      x = np.clip(x, x_nat - self.epsilon, x_nat + self.epsilon)
      x = np.clip(x, self.x_min, self.x_max) # ensure valid pixel range

    return x, np.linalg.norm(x - x_nat, ord=np.inf, axis=1), sess.run(self.detector.logits, feed_dict={self.detector.x_input: x})


class MadryLinfPGDAttackClassifier:
  def __init__(self, classifier, epsilon, num_steps, step_size, random_start, loss_func, x_min, x_max):
    """Attack parameter initialization. The attack performs k steps of
       size a, while always staying within epsilon from the initial
       point."""
    self.classifier = classifier
    self.epsilon = epsilon
    self.num_steps = num_steps
    self.step_size = step_size
    self.rand = random_start
    self.x_min = x_min
    self.x_max = x_max

    if loss_func == 'xent':
      loss = classifier.xent
    elif loss_func == 'cw':
      label_mask = tf.one_hot(classifier.y_input,
                              10,
                              on_value=1.0,
                              off_value=0.0,
                              dtype=tf.float32)
      correct_logit = tf.reduce_sum(label_mask * classifier.logits, axis=1)
      wrong_logit = tf.reduce_max((1-label_mask) * classifier.logits - 1e4*label_mask, axis=1)
      loss = -tf.nn.relu(correct_logit - wrong_logit + 50)
    else:
      print('Unknown loss function. Defaulting to cross-entropy')
      loss = classifier.xent

    self.grad = tf.gradients(loss, classifier.x_input)[0]

  def perturb(self, x_nat, y, sess):
    """Given a set of examples (x_nat, y), returns a set of adversarial
       examples within epsilon of x_nat in l_infinity norm."""
    if self.rand:
      x = x_nat + np.random.uniform(-self.epsilon, self.epsilon, x_nat.shape)
      #x = np.clip(x, self.x_min, self.x_max) # ensure valid pixel range
    else:
      x = np.copy(x_nat)

    for i in range(self.num_steps):
      grad = sess.run(self.grad, feed_dict={self.classifier.x_input: x,
                                            self.classifier.y_input: y})

      x = np.add(x, self.step_size * np.sign(grad), out=x, casting='unsafe')

      x = np.clip(x, x_nat - self.epsilon, x_nat + self.epsilon)
      x = np.clip(x, self.x_min, self.x_max) # ensure valid pixel range

    return x


class MadryPGDAttackDetector(PGDAttack):
  def __init__(self, target_class, **kwargs):
    super().__init__(**kwargs)

    self.x_image = tf.reshape(self.x, [-1, 28, 28, 1])

    with tf.variable_scope('madry', reuse=tf.AUTO_REUSE):
      # first convolutional layer
      W_conv1 = self._weight_variable([5,5,1,32])
      b_conv1 = self._bias_variable([32])

      h_conv1 = tf.nn.relu(self._conv2d(self.x_image, W_conv1) + b_conv1)
      h_pool1 = self._max_pool_2x2(h_conv1)

      # second convolutional layer
      W_conv2 = self._weight_variable([5,5,32,64])
      b_conv2 = self._bias_variable([64])

      h_conv2 = tf.nn.relu(self._conv2d(h_pool1, W_conv2) + b_conv2)
      h_pool2 = self._max_pool_2x2(h_conv2)

      # first fully connected layer
      W_fc1 = self._weight_variable([7 * 7 * 64, 1024])
      b_fc1 = self._bias_variable([1024])

      h_pool2_flat = tf.reshape(h_pool2, [-1, 7 * 7 * 64])
      h_fc1 = tf.nn.relu(tf.matmul(h_pool2_flat, W_fc1) + b_fc1)

      # output layer
      W_fc2 = self._weight_variable([1024,10])
      b_fc2 = self._bias_variable([10])

      self.pre_softmax = tf.matmul(h_fc1, W_fc2) + b_fc2

      self.y_pred = tf.argmax(self.pre_softmax, 1)

      correct_prediction = tf.equal(self.y_pred, self.y)

      self.num_correct = tf.reduce_sum(tf.cast(correct_prediction, tf.int64))
      self.accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

    self.detector_logits = self.pre_softmax[:, target_class]
    if kwargs['optimizer'] == 'normgrad':
      labels = tf.zeros_like(self.detector_logits)
      self.loss = -tf.reduce_sum(
        tf.nn.sigmoid_cross_entropy_with_logits(labels=labels, logits=self.detector_logits))
    else:
      self.loss = tf.reduce_sum(-self.detector_logits)
    self.setup_optimizer()

  @staticmethod
  def _weight_variable(shape):
      initial = tf.truncated_normal(shape, stddev=0.1)
      return tf.Variable(initial)

  @staticmethod
  def _bias_variable(shape):
      initial = tf.constant(0.1, shape = shape)
      return tf.Variable(initial)

  @staticmethod
  def _conv2d(x, W):
      return tf.nn.conv2d(x, W, strides=[1,1,1,1], padding='SAME')

  @staticmethod
  def _max_pool_2x2( x):
      return tf.nn.max_pool(x,
                            ksize = [1,2,2,1],
                            strides=[1,2,2,1],
                            padding='SAME')


class MadryPGDAttackClassifier(PGDAttack):
  def __init__(self, loss_fn, **kwargs):
    super().__init__(**kwargs)

    self.x_image = tf.reshape(self.x, [-1, 28, 28, 1])

    with tf.variable_scope('madry', reuse=tf.AUTO_REUSE):
      # first convolutional layer
      W_conv1 = self._weight_variable([5,5,1,32])
      b_conv1 = self._bias_variable([32])

      h_conv1 = tf.nn.relu(self._conv2d(self.x_image, W_conv1) + b_conv1)
      h_pool1 = self._max_pool_2x2(h_conv1)

      # second convolutional layer
      W_conv2 = self._weight_variable([5,5,32,64])
      b_conv2 = self._bias_variable([64])

      h_conv2 = tf.nn.relu(self._conv2d(h_pool1, W_conv2) + b_conv2)
      h_pool2 = self._max_pool_2x2(h_conv2)

      # first fully connected layer
      W_fc1 = self._weight_variable([7 * 7 * 64, 1024])
      b_fc1 = self._bias_variable([1024])

      h_pool2_flat = tf.reshape(h_pool2, [-1, 7 * 7 * 64])
      h_fc1 = tf.nn.relu(tf.matmul(h_pool2_flat, W_fc1) + b_fc1)

      # output layer
      W_fc2 = self._weight_variable([1024,10])
      b_fc2 = self._bias_variable([10])

      self.pre_softmax = tf.matmul(h_fc1, W_fc2) + b_fc2

      self.y_pred = tf.argmax(self.pre_softmax, 1)

      correct_prediction = tf.equal(self.y_pred, self.y)

      self.num_correct = tf.reduce_sum(tf.cast(correct_prediction, tf.int64))
      self.accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

    if loss_fn == 'xent':
      assert False
      self.loss = -tf.reduce_sum(classifier.y_xent)
    elif loss_fn == 'cw':
      label_mask = tf.one_hot(self.y, 10, dtype=tf.float32)
      correct_logit = tf.reduce_sum(label_mask * self.pre_softmax, axis=1)
      self.wrong_class = tf.argmax((1 - label_mask) * self.pre_softmax - 1e4 * label_mask, axis=1)
      wrong_logit = tf.reduce_max((1 - label_mask) * self.pre_softmax - 1e4 * label_mask, axis=1)
      self.loss = tf.reduce_sum(correct_logit - wrong_logit)
    self.setup_optimizer()

  @staticmethod
  def _weight_variable(shape):
      initial = tf.truncated_normal(shape, stddev=0.1)
      return tf.Variable(initial)

  @staticmethod
  def _bias_variable(shape):
      initial = tf.constant(0.1, shape = shape)
      return tf.Variable(initial)

  @staticmethod
  def _conv2d(x, W):
      return tf.nn.conv2d(x, W, strides=[1,1,1,1], padding='SAME')

  @staticmethod
  def _max_pool_2x2( x):
      return tf.nn.max_pool(x,
                            ksize = [1,2,2,1],
                            strides=[1,2,2,1],
                            padding='SAME')


class MadryClassifier(object):
  def __init__(self, var_scope):
    self.var_scope = var_scope
    self.output_size = 10
    self.x_input = tf.placeholder(tf.float32, shape = [None, 784])
    self.y_input = tf.placeholder(tf.int64, shape = [None])

    self.pre_softmax = self.forward(self.x_input)
    self.logits = self.pre_softmax


    y_xent = tf.nn.sparse_softmax_cross_entropy_with_logits(
        labels=self.y_input, logits=self.pre_softmax)

    self.xent = tf.reduce_sum(y_xent)

    self.y_pred = tf.argmax(self.pre_softmax, 1)
    self.predictions = self.y_pred

    correct_prediction = tf.equal(self.y_pred, self.y_input)

    self.num_correct = tf.reduce_sum(tf.cast(correct_prediction, tf.int64))
    self.accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

  def forward(self, x):
    with tf.variable_scope(self.var_scope, reuse=tf.AUTO_REUSE):
      # first convolutional layer
      W_conv1 = tf.get_variable('Variable', [5,5,1,32])
      b_conv1 = tf.get_variable('Variable_1', [32])

      x_image = tf.reshape(x, [-1, 28, 28, 1])
      h_conv1 = tf.nn.relu(self._conv2d(x_image, W_conv1) + b_conv1)
      h_pool1 = self._max_pool_2x2(h_conv1)

      # second convolutional layer
      W_conv2 = tf.get_variable('Variable_2', [5,5,32,64])
      b_conv2 = tf.get_variable('Variable_3', [64])

      h_conv2 = tf.nn.relu(self._conv2d(h_pool1, W_conv2) + b_conv2)
      h_pool2 = self._max_pool_2x2(h_conv2)

      # first fully connected layer
      W_fc1 = tf.get_variable('Variable_4', [7 * 7 * 64, 1024])
      b_fc1 = tf.get_variable('Variable_5', [1024])

      h_pool2_flat = tf.reshape(h_pool2, [-1, 7 * 7 * 64])
      h_fc1 = tf.nn.relu(tf.matmul(h_pool2_flat, W_fc1) + b_fc1)

      # output layer
      W_fc2 = tf.get_variable('Variable_6', [1024,10])
      b_fc2 = tf.get_variable('Variable_7', [10])

      pre_softmax = tf.matmul(h_fc1, W_fc2) + b_fc2
      return pre_softmax

  @staticmethod
  def _conv2d(x, W):
      return tf.nn.conv2d(x, W, strides=[1,1,1,1], padding='SAME')

  @staticmethod
  def _max_pool_2x2( x):
      return tf.nn.max_pool(x,
                            ksize = [1,2,2,1],
                            strides=[1,2,2,1],
                          padding='SAME')
