from dataclasses import replace
import pytest
from instrumentdesk.consignment_eval.service import check_point, prepare_verification, performance, stable_loss, boundary_diagnostics, sector_replay


def test_loss_is_finite_at_probability_limits():
    # TRAP-31
    assert stable_loss(0,1) == pytest.approx(27.6310211159)
    assert stable_loss(1,0) == pytest.approx(27.6310432379)


def test_no_outcome_gets_undefined_metrics(prediction):
    # TRAP-43
    row = replace(prediction,outcome=None)
    metric = performance([check_point(row,prepare_verification([]))])
    assert (metric.status,metric.count,metric.mae,metric.error) == ('NO_MATURE_RESULT',0,None,None)


def test_empty_calibration_requires_review(prediction):
    # TRAP-44
    checked = check_point(prediction,prepare_verification([]))
    assert checked.uncertain and checked.lower is None


def test_first_class_only_is_sparse(prediction):
    negatives = [replace(prediction,score=.25,outcome=0,observed=True)] * 12
    assert prepare_verification(negatives).method == 'sparse-risk'
    metric = performance([check_point(p,prepare_verification(negatives)) for p in negatives])
    assert metric.auxiliary == 0 and metric.status == 'NO_POSITIVES'


def test_fitted_calibrator_is_order_preserving(prediction):
    observed = [replace(prediction,key=f'k{i}',score=i/20,outcome=int(i>=10),observed=True) for i in range(1,19)]
    trained = prepare_verification(observed)
    estimates = [check_point(row,trained).estimate for row in observed]
    assert all(0<=estimate<=1 for estimate in estimates)
    assert estimates == sorted(estimates) and trained.size == 18
    assert not any(check_point(row,trained).uncertain for row in observed)


def test_censored_target_does_not_fit_error_band(prediction):
    point = replace(prediction,observed=False,outcome=0)
    assert prepare_verification([point]).size == 0


def test_cutoff_confusion_counts_have_exact_boundaries(prediction):
    verified = [check_point(replace(prediction,score=value,outcome=target,observed=True),prepare_verification([]))
                for value,target in [(0.2,1),(0.5,0),(0.8,1)]]
    actual=boundary_diagnostics(verified,.5)
    assert (actual['实绩超线'],actual['估计超线'],actual['额外复测'],actual['漏查']) == (2,2,1,1)
    assert len(sector_replay(verified,.5)) == 5
