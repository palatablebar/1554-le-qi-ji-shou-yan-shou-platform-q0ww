import pytest
from instrumentdesk.pipeline import open_fixture
from instrumentdesk.consignment_notes.service import load_samples
from instrumentdesk.return_observation.service import build_windows
from instrumentdesk.instrument_evidence.service import fit_features, transform_windows
from instrumentdesk.return_prior_claim.service import fit_model, predict


@pytest.fixture
def observation():
    return dict(open_fixture()['records'][0])


@pytest.fixture(scope='session')
def fitted_vectors():
    sample = open_fixture()
    intake = load_samples(sample['records'],sample['as_of'])
    windows = build_windows(intake.entries)
    reference = fit_features(windows.train)
    prepared = transform_windows(windows,reference)
    return prepared.train, prepared.live, reference.fingerprint


@pytest.fixture(scope='session')
def prediction(fitted_vectors):
    train, live, stamp = fitted_vectors
    anchor = fit_model(train,stamp)
    inferred = predict(anchor,live[:1],stamp)[0]
    return inferred
