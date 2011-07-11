======
Themes
======

Every opinion created on Firefox Input is published to GrouperFish a RESTful
text-clustering service from Mozilla Metrics.

Periodically we can update our clusters (or themes) locally with a cron task.

These themes are stored in ElasticSearch.

.. _gf-servers:

Servers
-------
Mozilla Metrics hosts an instance of GrouperFish at:

    http://node21.generic.metrics.sjc1.mozilla.com:8030

How Data Gets into GrouperFish
------------------------------

Through the use of `post_save` signals on the :class:`feedback.models.Opinion`
model we can send data to GrouperFish asynchronously via Celery.

Initializing GrouperFish
------------------------

If we need to initialize a GrouperFish cluster with old data we can use the
`grouperfish_index_all` cron script.  It sends data to the GrouperFish instance
in batches of 1000.

Grouperfish Settings
--------------------
.. module:: django.conf.settings

.. data:: GF_HOST

    This is the host for GrouperFish.  See :ref:`gf-servers`.

.. data:: GF_NAMESPACE

    This is the namespace or index that we use.  Things in this index are
    partitioned off from other namespaces.  This makes it very easy to have
    multiple GrouperFish datasets hosted on a single cluster.  E.g. `input`,
    `input-stage`, `input-dev`.

Polling for clusters
--------------------

Grouperfish clusters the data periodically and can be polled for new data.  We
do this with the ``update_clusters`` cron command.

Handling Failure
----------------

Since themes is dependent on ElasticSearch, we need to handle two cases:

1. ElasticSearch isn't enabled.
2. ElasticSearch is enabled, but the host is not reachable.

Rather than publish a standard 500 error, we should give the user something a
bit more informative.

ElasticSearch Disabled
~~~~~~~~~~~~~~~~~~~~~~

ElasticSearch can be disabled (see
:ref:`ES_DISABLED <elasticutils:installation>`).  Therefore a `501` error
should be raised with an explanation that this particular instance of Firefox
Input does not have Themes implemented.

ElasticSearch Missing
~~~~~~~~~~~~~~~~~~~~~

Another failur case is that the ElasticSearch is not being responsive.  In
which case we should raise a `503` error explaining that we are temporarily
having trouble finding themes.

Todo
----

* Configurable batch sizes
