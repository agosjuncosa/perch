# coding=utf-8
# Copyright 2023 The Chirp Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Embed UH reef data."""

from chirp import config_utils
from ml_collections import config_dict

_c = config_utils.callable_config
_object_config = config_utils.object_config


def get_config() -> config_dict.ConfigDict:
  """Create the inference config."""
  config = config_dict.ConfigDict()

  config.output_dir = 'output_dir'
  config.source_file_patterns = ['wav_dir/*.wav']
  model_checkpoint_path = ''

  config.num_shards_per_file = 1
  config.embed_fn_config = {
      'write_embeddings': True,
      'write_logits': False,
      'write_separated_audio': False,
      'write_raw_audio': False,
      'model_key': 'taxonomy_model_tf',
      'model_config': {
          'model_path': model_checkpoint_path,
          'window_size_s': 5.0,
          'hop_size_s': 3.0,
          'sample_rate': 32000,
      },
  }
  return config