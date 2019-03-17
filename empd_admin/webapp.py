import os
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.web
import tempfile

import empd_admin.repo_test as test


class TestHookHandler(tornado.web.RequestHandler):
    def post(self):
        headers = self.request.headers
        event = headers.get('X-GitHub-Event', None)

        if event == 'ping':
            self.write('pong')
        elif event == 'pull_request':
            body = tornado.escape.json_decode(self.request.body)
            repo_name = body['repository']['name']
            repo_url = body['repository']['clone_url']
            owner = body['repository']['owner']['login']
            pr_id = int(body['pull_request']['number'])
            is_open = body['pull_request']['state'] == 'open'

            # Only do anything if we are working with EMPD2, and an open PR.
            if is_open and owner == 'EMPD2':
                self.write("testing PR %i from %s/%s" % (
                    pr_id, owner, repo_name))

                with tempfile.TemporaryDirectory('_empd') as tmp_dir:
                    test_info = test.download_pr(
                        owner, repo_name, pr_id, tmp_dir)

                    # display information on the PR to the user
                    if not test_info:
                        test_info = test.pr_info(tmp_dir)
                        if test_info:
                            msg = test.comment_on_pr(
                                owner, repo_name, pr_id, test_info['message'],
                                onlyif='any',
                                force=(test_info['status'] == 'failure'))
                            test.set_pr_status(owner, repo_name, test_info,
                                               target_url=msg.html_url)

                        # run the tests
                        test_info = test.full_repo_test(local_repo)

                if test_info:
                    msg = test.comment_on_pr(
                        owner, repo_name, pr_id, test_info['message'])
                    test.set_pr_status(owner, repo_name, test_info,
                                       target_url=msg.html_url)
        else:
            print('Unhandled event "{}".'.format(event))
            self.set_status(404)
            self.write_error(404)


def create_webapp():
    application = tornado.web.Application([
        (r"/empd-data/hook", TestHookHandler),
    ])
    return application


def main():
    application = create_webapp()
    http_server = tornado.httpserver.HTTPServer(application, xheaders=True)
    port = int(os.environ.get("PORT", 5000))

    # https://devcenter.heroku.com/articles/optimizing-dyno-usage#python
    n_processes = int(os.environ.get("WEB_CONCURRENCY", 1))

    if n_processes != 1:
        # http://www.tornadoweb.org/en/stable/guide/running.html#processes-and-ports
        http_server.bind(port)
        http_server.start(n_processes)
    else:
        http_server.listen(port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
