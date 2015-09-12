import copy

import numpy

from smqtk.iqr_index import IqrIndex
from smqtk.utils import SimpleTimer
from smqtk.utils.distance_kernel import (
    compute_distance_kernel,
    compute_distance_matrix
)
from smqtk.utils.distance_functions import histogram_intersection_distance2
import smqtk.utils.plugin as plugin

try:
    import svm
    import svmutil
except ImportError:
    svm = None
    svmutil = None


__author__ = 'purg'


class LibSvmHikIqrIndex (IqrIndex):
    """
    Uses libSVM python interface, using histogram intersection, to implement
    IQR ranking.
    """

    # Dictionary of parameter/value pairs that will be passed to libSVM during
    # the model trail phase. Parameters that are flags, i.e. have no values,
    # should be given an empty string ('') value.
    SVM_TRAIN_PARAMS = {
        '-q': '',
        '-t': 5,  # Specified the use of HI kernel, 5 is unique to custom build
        '-b': 1,
        '-c': 2,
        '-g': 0.0078125,
    }

    @classmethod
    def is_usable(cls):
        """
        Check whether this implementation is available for use.

        Required valid presence of svm and svmutil modules

        :return: Boolean determination of whether this implementation is usable.
        :rtype: bool

        """
        return svm and svmutil

    def __init__(self):
        """
        TODO ::
        - input optional known background descriptors, i.e. descriptors for
            things that would otherwise always be considered a negative example.

        """
        # Descriptor elements in this index
        self._descr_cache = []
        # Local serialization of descriptor vectors. Used when for computing
        # distances of SVM support vectors for Platt Scaling
        self._descr_matrix = None
        # Mapping of descriptor vectors to their index in the cache, and
        # subsequently in the distance kernel
        self._descr2index = {}
        # Distance kernel matrix (symmetric)
        self._dist_kernel = None

        # TODO: make cache file constructor parameters + load them if they
        #       exist

    @staticmethod
    def _gen_w1_weight(num_pos, num_neg):
        """
        Return w1 weight parameter based on pos and neg exemplars
        """
        return max(1.0, num_neg/float(num_pos))

    @classmethod
    def _gen_svm_parameter_string(cls, num_pos, num_neg):
        params = copy.copy(cls.SVM_TRAIN_PARAMS)
        params['-w1'] = cls._gen_w1_weight(num_pos, num_neg)
        return ' '.join((' '.join((str(k), str(v))) for k, v in params.items()))

    def get_config(self):
        return {}

    def count(self):
        return len(self._descr_cache)

    def build_index(self, descriptors):
        """
        Build the index based on the given iterable of descriptor elements.

        Subsequent calls to this method should rebuild the index, not add to it.

        :raises ValueError: No data available in the given iterable.

        :param descriptors: Iterable of descriptor elements to build index over.
        :type descriptors: collections.Iterable[smqtk.data_rep.DescriptorElement]

        """
        # TODO: Refuse to build if we already have data models loaded
        #       so we don't overwrite them in persistent storage

        # ordered cache of descriptors in our index.
        self._descr_cache = []
        # Reverse mapping of a descriptor's vector to its index in the cache
        # and subsequently in the distance kernel.
        self._descr2index = {}
        # matrix for creating distance kernel
        self._descr_matrix = []
        for i, d in enumerate(descriptors):
            v = d.vector()
            self._descr_cache.append(d)
            self._descr_matrix.append(v)
            self._descr2index[tuple(v)] = i
        self._descr_matrix = numpy.array(self._descr_matrix)
        # TODO: For when we optimize SVM SV kernel computation
        #descr_matrix = numpy.array(descr_matrix)
        #self._dist_kernel = \
        #    compute_distance_kernel(descr_matrix,
        #                            histogram_intersection_distance2,
        #                            row_wise=True)

    def rank(self, pos, neg=()):
        """
        Rank the currently indexed elements given ``pos`` positive and ``neg``
        negative exemplar descriptor elements.

        :param pos: Iterable of positive exemplar DescriptorElement instances.
        :type pos: collections.Iterable[smqtk.data_rep.DescriptorElement]

        :param neg: Optional iterable of negative exemplar DescriptorElement
            instances.
        :type neg: collections.Iterable[smqtk.data_rep.DescriptorElement]

        :return: Map of descriptor UUID to rank value within [0, 1] range, where
            a 1.0 means most relevant and 0.0 meaning least relevant.
        :rtype: dict[collections.Hashable, float]

        """
        # Notes:
        # - Pos and neg exemplars may be in our index.

        #
        # Process
        #
        # - create training matrix of indexed and input descriptors
        #     train_labels = []; train_vectors = []
        #     for d in (pos + neg):
        #         if in pos: train_labels.append(+1)
        #         else     : train_labels.append(-1)
        #         train_vectors.append(d.vector().tolist())  # because libSVM wants lists
        # - compute svm problem/model
        #     svm_problem = svm.svm_problem(train_labels, train_vectors)
        #     svm_model = svmutil.svm_train(svm_problem, <parameter string>)
        # - get out support vectors (actual descriptors)
        #     svm_sv = [[i.value for i in n[:m.shape[1]]] for n in svm_model.SV[:sum(svm_model.nSV[:2])]]
        # - compute distance of support vectors to everything in index
        #   -> or, of support vectors are really always either a query vector
        #      or something in our existing index, get the specific rows from
        #      pre-existing distance kernel(s).
        #     svm_test_k = compute_distance_matrix(svm_sv, m, histogram_intersection_distance2, True)
        # - Platt Scaling (see original code, it doesn't need change)

        # TODO: Pad the negative list with something when empty, else SVM
        #       training is going to fail.

        #
        # SVM model training
        #
        train_labels = []
        train_vectors = []
        for d in pos:
            train_labels.append(+1)
            train_vectors.append(d.vector().tolist())
        for d in neg:
            train_labels.append(-1)
            train_vectors.append(d.vector().tolist())

        svm_problem = svm.svm_problem(train_labels, train_vectors)
        svm_model = svmutil.svm_train(svm_problem, self._gen_svm_parameter_string(len(pos), len(neg)))

        #
        # Platt Scaling for probability rankings
        #

        # Number of support vectors
        num_SVs = sum(svm_model.nSV[:svm_model.nr_class])
        # Support vector dimensionality
        dim_SVs = len(train_vectors[0])
        # initialize matrix they're going into
        svm_SVs = numpy.ndarray((num_SVs, dim_SVs), dtype=float)
        for i, nlist in enumerate(svm_model.SV[:svm_SVs.shape[0]]):
            svm_SVs[i, :] = [n.value for n in nlist[:len(train_vectors[0])]]
        # compute matrix of distances from support vectors to index elements
        # TODO: Optimize this so we don't perform repeat distance calculations
        #       for intra-index vectors.
        svm_test_k = compute_distance_matrix(svm_SVs, self._descr_matrix,
                                             histogram_intersection_distance2,
                                             row_wise=True)

        # the actual platt scaling stuff
        weights = numpy.array(svm_model.get_sv_coef()).flatten()
        margins = numpy.dot(weights, svm_test_k)
        rho = svm_model.rho[0]
        probA = svm_model.probA[0]
        probB = svm_model.probB[0]
        probs = 1.0 / (1.0 + numpy.exp((margins - rho) * probA + probB))

        return dict(zip(self._descr_cache, probs))


IQR_INDEX_CLASS = LibSvmHikIqrIndex
