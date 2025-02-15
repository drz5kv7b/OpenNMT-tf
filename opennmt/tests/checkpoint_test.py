import os

import tensorflow as tf

from opennmt.utils import checkpoint as checkpoint_util


class _DummyModel(tf.keras.layers.Layer):

  def __init__(self):
    super(_DummyModel, self).__init__()
    self.layers = [tf.keras.layers.Dense(20), tf.keras.layers.Dense(20)]

  def call(self, x):
    for layer in self.layers:
      x = layer(x)
    return x


class CheckpointTest(tf.test.TestCase):

  def testCheckpointAveraging(self):
    model = _DummyModel()
    optimizer = tf.keras.optimizers.Adam()

    @tf.function
    def _build_model():
      x = tf.random.uniform([4, 10])
      y = model(x)
      loss = tf.reduce_mean(y)
      gradients = optimizer.get_gradients(loss, model.trainable_variables)
      optimizer.apply_gradients(zip(gradients, model.trainable_variables))

    def _assign_var(var, scalar):
      var.assign(tf.ones_like(var) * scalar)

    def _all_equal(var, scalar):
      return tf.size(tf.where(tf.not_equal(var, scalar))).numpy() == 0

    def _get_var_list(checkpoint_path):
      return [name for name, _ in tf.train.list_variables(checkpoint_path)]

    _build_model()

    # Write some checkpoint with all variables set to the step value.
    steps = [10, 20, 30, 40]
    num_checkpoints = len(steps)
    avg_value = sum(steps) / num_checkpoints
    directory = os.path.join(self.get_temp_dir(), "src")
    checkpoint = tf.train.Checkpoint(model=model, optimizer=optimizer)
    checkpoint_manager = tf.train.CheckpointManager(
        checkpoint, directory, max_to_keep=num_checkpoints)
    for step in steps:
      _assign_var(model.layers[0].kernel, step)
      _assign_var(model.layers[0].bias, step)
      checkpoint_manager.save(checkpoint_number=step)

    output_dir = os.path.join(self.get_temp_dir(), "dst")
    checkpoint_util.average_checkpoints(
        directory, output_dir, dict(model=model, optimizer=optimizer))
    avg_checkpoint = tf.train.latest_checkpoint(output_dir)
    self.assertIsNotNone(avg_checkpoint)
    checkpoint.restore(avg_checkpoint)
    self.assertTrue(_all_equal(model.layers[0].kernel, avg_value))
    self.assertTrue(_all_equal(model.layers[0].bias, avg_value))
    self.assertListEqual(
        _get_var_list(avg_checkpoint),
        _get_var_list(checkpoint_manager.latest_checkpoint))


if __name__ == "__main__":
  tf.test.main()
