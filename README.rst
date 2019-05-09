==========
MDict Tool
==========

MDict pack/unpack tool

.. NOTE::

    Support MIT and 996.icu license

Install
=======
::

    pip install mdict-utils

Usage
=====
Meta information::

    mdict -m dict.mdx

All key list::

    mdict -k dict.mdx

All key list::

    mdict -k dict.mdx

Query key::

    mdict -q <word> dict.mdx

.. note::

    只用于测试词典打包是否正确。

Unpack
------
Unpack MDX::

    mdict -x dict.mdx -d ./mdx

Unpack MDX/MDD and split into 5 files::

    mdict -x dict.mdx -d ./mdx --split-n 5

Unpack MDX/MDD and split into a...z files::

    mdict -x dict.mdx -d ./mdx --split-az

Unpack MDD::

    mdict -x dict.mdd -d ./mdd

Unpack MDX/MDD to sqlite3 DB::

    mdict -x dict.mdx --exdb
    mdict -x dict.mdd --exdb

Unpack MDX/MDD to sqlite3 DB with zip compress::

    mdict -x dict.mdx --exdb-zip

Pack
----
Pack MDX::

    mdict --title title.html --description description.html -a dict.txt dict.mdx

Pack MDX with many TXT files::

    mdict --title title.html --description description.html -a dict.part1.txt -a dict.part2.txt dict.mdx

or::

    mdict --title title.html --description description.html -a txt_dir dict.mdx

Pack MDD::

    mdict --title title.html --description description.html -a mdd_dir dict.mdd

Other
-----
Convert TXT to sqlite3 DB::

    mdict --txt-db dict.txt

Convert sqlite3 DB to TXT::

    mdict --db-txt dict.db


Reference
=========

+   https://bitbucket.org/xwang/mdict-analysis
+   https://github.com/zhansliu/writemdict

Donate 捐赠
=============

.. image:: alipay_pay.jpg
    :width: 45%
.. image:: wx_pay.png
    :width: 45%
