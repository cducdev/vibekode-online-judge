(function () {
    'use strict';

    var relativeTime = new Intl.RelativeTimeFormat(document.documentElement.lang || 'en', {numeric: 'auto'});
    var pointFormat = new Intl.NumberFormat(document.documentElement.lang || 'en', {
        maximumFractionDigits: 3,
    });

    function relativeDate(isoDate) {
        var seconds = Math.round((new Date(isoDate).getTime() - Date.now()) / 1000);
        var absolute = Math.abs(seconds);
        if (absolute < 60) return relativeTime.format(seconds, 'second');
        if (absolute < 3600) return relativeTime.format(Math.round(seconds / 60), 'minute');
        if (absolute < 86400) return relativeTime.format(Math.round(seconds / 3600), 'hour');
        return relativeTime.format(Math.round(seconds / 86400), 'day');
    }

    function makeLink(className, href, text) {
        var link = document.createElement('a');
        link.className = className;
        link.href = href;
        link.textContent = text;
        return link;
    }

    function makeUserIdentity(submission) {
        var identity = document.createElement('div');
        identity.className = 'contest-live-submission-identity';

        var displayName = submission.user.display_name || submission.user.name || submission.user.username;
        var fullName = submission.user.full_name;
        var showProfileDecoration = !fullName;
        var userLine = document.createElement('span');
        userLine.className = 'contest-live-submission-user';
        if (showProfileDecoration) userLine.className += ' ' + submission.user.css_class;
        var user = makeLink(
            'contest-live-submission-user-link',
            submission.user.url,
            fullName || displayName
        );
        user.title = fullName ? fullName + ' (@' + submission.user.username + ')' : submission.user.username;
        userLine.appendChild(user);
        if (showProfileDecoration && submission.user.badge && submission.user.badge.image_url) {
            var badge = document.createElement('img');
            badge.className = 'contest-live-submission-user-badge';
            badge.src = submission.user.badge.image_url;
            badge.alt = '';
            badge.title = submission.user.badge.name;
            userLine.appendChild(badge);
        }
        identity.appendChild(userLine);

        var organization = submission.user.organization;
        if (organization) {
            var meta = document.createElement('div');
            meta.className = 'contest-live-submission-meta';
            var organizationLink = makeLink(
                'contest-live-submission-organization',
                organization.url,
                organization.short_name
            );
            organizationLink.title = organization.name;
            meta.appendChild(organizationLink);
            identity.appendChild(meta);
        }
        return identity;
    }

    function makeSubmissionRow(submission) {
        var row = document.createElement('li');
        row.className = 'contest-live-submission';

        var identity = makeUserIdentity(submission);

        var problem = makeLink(
            'contest-live-submission-problem',
            submission.problem.url,
            submission.problem.label
        );
        problem.title = submission.problem.name;

        var result = makeLink(
            'contest-live-submission-result ' + submission.result_class,
            submission.url,
            ''
        );
        var pointText = submission.points === null ? '\u2014' : pointFormat.format(submission.points);
        if (!submission.is_graded) {
            var spinner = document.createElement('i');
            spinner.className = 'fa fa-spinner fa-pulse';
            spinner.setAttribute('aria-hidden', 'true');
            result.appendChild(spinner);
        }
        var resultText = document.createElement('span');
        resultText.textContent = submission.status_display + ' \u00b7 ' + pointText;
        result.appendChild(resultText);
        result.title = submission.status_label + ' \u00b7 ' + pointText;
        result.setAttribute('aria-label', result.title);

        var submitted = document.createElement('time');
        submitted.className = 'contest-live-submission-time';
        submitted.dateTime = submission.submitted_at;
        submitted.textContent = relativeDate(submission.submitted_at);

        row.appendChild(identity);
        row.appendChild(problem);
        row.appendChild(result);
        row.appendChild(submitted);
        return row;
    }

    function initFeed(feed) {
        var list = feed.querySelector('[data-live-submissions-list]');
        var empty = feed.querySelector('[data-live-submissions-empty]');
        var state = feed.querySelector('[data-live-submissions-state]');
        var timer = null;
        var loading = false;
        var knownSubmissionIds = new Set();
        var hasRendered = false;

        function setState(label) {
            state.textContent = label;
        }

        function schedule(delay) {
            window.clearTimeout(timer);
            timer = window.setTimeout(load, delay);
        }

        function render(payload) {
            var fragment = document.createDocumentFragment();
            var nextSubmissionIds = new Set();
            payload.submissions.forEach(function (submission, index) {
                var submissionId = String(submission.id);
                var row = makeSubmissionRow(submission);
                nextSubmissionIds.add(submissionId);
                if ((!hasRendered && index === 0) || (hasRendered && !knownSubmissionIds.has(submissionId))) {
                    row.classList.add('is-new');
                }
                fragment.appendChild(row);
            });
            list.replaceChildren(fragment);
            knownSubmissionIds = nextSubmissionIds;
            hasRendered = true;
            empty.hidden = payload.submissions.length !== 0;

            if (payload.frozen) {
                setState(feed.dataset.frozenLabel);
            } else if (payload.submissions.some(function (submission) { return !submission.is_graded; })) {
                setState(feed.dataset.judgingLabel);
            } else {
                setState(feed.dataset.liveLabel);
            }

            schedule(payload.next_poll_ms || 5000);
        }

        function load() {
            if (loading) return;
            if (feed.closest('[hidden]')) {
                schedule(10000);
                return;
            }

            loading = true;
            fetch(feed.dataset.feedUrl, {
                credentials: 'same-origin',
                headers: {'Accept': 'application/json'},
            }).then(function (response) {
                if (!response.ok) throw new Error('Live submissions request failed: ' + response.status);
                return response.json();
            }).then(render).catch(function () {
                setState(feed.dataset.errorLabel);
                schedule(5000);
            }).finally(function () {
                loading = false;
            });
        }

        feed.addEventListener('contest-live:show', function () {
            schedule(0);
        });

        if (window.event_dispatcher && feed.dataset.eventChannel) {
            window.event_dispatcher.auto_reconnect = true;
            window.event_dispatcher.on(feed.dataset.eventChannel, function () {
                schedule(100);
            });
        }

        window.setInterval(function () {
            list.querySelectorAll('time[datetime]').forEach(function (element) {
                element.textContent = relativeDate(element.dateTime);
            });
        }, 15000);

        setState(feed.dataset.loadingLabel);
        load();
    }

    function init() {
        document.querySelectorAll('[data-live-submissions]').forEach(initFeed);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
