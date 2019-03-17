import pytest
import os


@pytest.fixture(scope='session')
def gh():
    import github
    return github.Github(os.getenv('GH_TOKEN'))


@pytest.fixture(scope='session')
def owner(gh):
    return gh.get_user('EMPD2')


@pytest.fixture(scope='session')
def remote_repo(owner):
    return owner.get_repo('EMPD-data')


@pytest.fixture(scope='session')
def pr_id():
    # https://github.com/EMPD2/EMPD-data/pull/2
    return 2


@pytest.fixture
def local_repo(remote_repo, tmpdir):
    from git import Repo
    repo = Repo.clone_from(remote_repo.clone_url, tmpdir)
    repo.git.checkout('test-data')
    return repo
