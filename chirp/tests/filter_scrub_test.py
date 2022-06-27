# coding=utf-8
# Copyright 2022 The Chirp Authors.
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

"""Tests for xeno_canto."""

import functools
import shutil
import tempfile

from chirp.data import filter_scrub_utils as fsu
from chirp.tests import fake_dataset
import pandas as pd
import tensorflow_datasets as tfds

from absl.testing import absltest


class FilterScrubTest(absltest.TestCase):
  """Used to factorize the common setup between different types of queries."""

  def setUp(self):
    super().setUp()
    # We define a toy dataframe that is easy to manually check
    self.toy_df = pd.DataFrame({
        'species_code': ['ostric2', 'ostric3', 'grerhe1'],
        'Common name': ['Common Ostrich', 'Somali Ostrich', 'Greater Rhea'],
        'bg_labels': [['ostric3', 'grerhe1'], ['ostric2', 'grerhe1'],
                      ['ostric2', 'ostric3']],
        'Country': ['Colombia', 'Australia', 'France'],
    })

    # Additionally, we define a dataframe that mimics the actual dataset
    # of interest. Test will be carried out on both dataframes.
    self.temp_dir = tempfile.mkdtemp()
    # self.temp_dir = self.create_tempdir()
    # create_tempdir() raises an UnparsedFlagAccessError when debugged locally,
    # Using `tempdir` instead and manually deleting the folder after test.
    fake_builder = fake_dataset.FakeDataset(data_dir=self.temp_dir)
    fake_builder.download_and_prepare()
    self.fake_df = tfds.as_dataframe(fake_builder.as_dataset()['train'])

  def tearDown(self):
    super().tearDown()
    shutil.rmtree(self.temp_dir)


class NotInTests(FilterScrubTest):

  def test_filtering_ideal(self):
    """Ensure filtering produces expected results in nominal case."""

    # 1) Tests on the toy dataFrame.
    test_df = self.toy_df.copy()
    fn_call = functools.partial(
        fsu.not_in, key='Country', values=['France', 'Brazil'])

    # Ensure we're properly filtering out species
    self.assertEqual(
        test_df.apply(fn_call, axis=1, result_type='expand').tolist(),
        [True, True, False])

    # 2) Tests on the fake dataFrame.

    df = self.fake_df.copy()
    targeted_country = b'South Africa'
    # If that doesn't pass, maybe South Africa is just no longer a good example
    # to test on. Check fake_dataset how the recordings are populated.
    self.assertIn(targeted_country, df['country'].unique())
    filtering_fn = functools.partial(
        fsu.not_in, key='country', values=[targeted_country])
    filtered_df = df[df.apply(filtering_fn, axis=1, result_type='expand')]
    self.assertGreater(len(df), len(filtered_df))

    # Ensure we've filtered all South African species.
    self.assertEqual(filtered_df['country'].isin([targeted_country]).sum(), 0)

    # Ensure we did not filter too many countries.
    self.assertEqual((df['country'] == targeted_country).sum(),
                     len(df) - len(filtered_df))

  def test_filtering_wrong_field(self):
    """Ensure filtering raises adequate error when the field does not exist."""
    test_df = self.toy_df.copy()

    # Make a query with an error in the name of the field
    with self.assertRaises(ValueError):
      test_df.apply(
          functools.partial(
              fsu.not_in, key='county', values=['France', 'Brazil']),
          axis=1,
          result_type='expand')

  def test_filtering_wrong_type(self):
    """Ensure filtering raises adequate error with wrong input type."""
    test_df = self.toy_df.copy()
    with self.assertRaises(TypeError):
      test_df.apply(
          functools.partial(
              fsu.not_in, key='Country', values=[b'France', b'Brazil']),
          axis=1,
          result_type='expand')


class ScrubTest(FilterScrubTest):

  def test_scrubbing_ideal(self):
    """Ensure scrubbing works as expected in nominal case."""
    expected_df = self.toy_df.copy()
    expected_df['bg_labels'] = [['grerhe1'], ['ostric2', 'grerhe1'],
                                ['ostric2']]

    # 1) Simple scrubbing queries on the toy dataframe
    test_df = self.toy_df.copy()
    test_df = test_df.apply(
        lambda row: fsu.scrub(row, 'bg_labels', ['ostric3']),
        axis=1,
        result_type='expand')
    self.assertEqual(expected_df.to_dict(), test_df.to_dict())

    # 2) Simple scrubbing queries on the fake_df
    df = self.fake_df.copy()
    targeted_country = b'South Africa'
    key = 'label'
    all_species = df[key].explode(key).unique()
    south_african_species = df[df['country'] == targeted_country][key].explode(
        key).unique()
    scrubbing_fn = functools.partial(
        fsu.scrub, key=key, values=south_african_species)
    scrubbed_df = df.apply(scrubbing_fn, axis=1, result_type='expand')

    remaining_species = scrubbed_df[key].explode(key).unique()
    self.assertEqual(
        set(south_african_species),
        set(all_species).difference(remaining_species))

  def test_scrubbing_empty_col(self):
    """Ensure scrubbing doesn't do anything if the column is empty."""

    expected_df = self.toy_df.copy()
    test_df = self.toy_df.copy()
    expected_df['bg_labels'] = [[], [], []]
    test_df['bg_labels'] = [[], [], []]
    test_df = test_df.apply(
        lambda row: fsu.scrub(row, 'bg_labels', ['ostric3']),
        axis=1,
        result_type='expand')
    self.assertEqual(expected_df.to_dict(), test_df.to_dict())

  def test_scrubbing_empty_query(self):
    """Ensure scrubbing doesn't do anything if `values` is an empty list."""

    expected_df = self.toy_df.copy()
    test_df = self.toy_df.copy()
    test_df = test_df.apply(
        lambda row: fsu.scrub(row, 'bg_labels', []),
        axis=1,
        result_type='expand')
    self.assertEqual(expected_df.to_dict(), test_df.to_dict())

  def test_scrub_no_side_effects(self):
    """Ensure scrubbing operation does not have side-effects."""
    df = self.fake_df.copy()
    key = 'label'
    # Scrub every foreground label.
    scrubbing_fn = functools.partial(
        fsu.scrub, key=key, values=df.explode(key)[key].unique())
    _ = df.apply(scrubbing_fn, axis=1, result_type='expand')

    # If scrub function had side-effects, e.g. modified the row in-place,
    # the df would also change.
    self.assertTrue(self.fake_df.equals(df))


if __name__ == '__main__':
  absltest.main()