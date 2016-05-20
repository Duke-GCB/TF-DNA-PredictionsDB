from unittest import TestCase
from pred.queries.maxpredictionquery import MaxPredictionQuery

MAX_QUERY_BASE = """SET search_path TO %s,public;
with max_prediction_names as (
 select name from gene_prediction
where
gene_list = %s
and
model_name = %s
and
case strand when '+' then
(txstart - %s) <= start_range and (txstart + %s) >= start_range
else
(txend - %s) <= end_range and (txend + %s) >= end_range
end{}
group by name
order by max(value) desc{}
)
select
max(common_name) as common_name,
name,
round(max(value), 4) as max_value,
max(chrom) as chrom,
max(strand) as strand,
max(case strand when '+' then txstart else txend end) as gene_start,
json_agg(json_build_object('value', round(value, 4), 'start', start_range, 'end', end_range)) as pred
from gene_prediction
where
gene_list = %s
and
model_name = %s
and
case strand when '+' then
(txstart - %s) <= start_range and (txstart + %s) >= start_range
else
(txend - %s) <= end_range and (txend + %s) >= end_range
end
and name in (select name from max_prediction_names)
group by name
order by max(value) desc, name"""

MAX_QUERY_WITH_GUESS_WITH_LIMIT = MAX_QUERY_BASE.format("\nand value > %s", "\nlimit %s offset %s")
MAX_QUERY_WITH_GUESS = MAX_QUERY_BASE.format("\nand value > %s", "")
MAX_QUERY_NO_GUESS_WITH_LIMIT = MAX_QUERY_BASE.format("", "\nlimit %s offset %s")
MAX_QUERY_NO_GUESS = MAX_QUERY_BASE.format("", "")

COUNT_QUERY = """SET search_path TO %s,public;
with max_prediction_names as (
 select name from gene_prediction
where
gene_list = %s
and
model_name = %s
and
case strand when '+' then
(txstart - %s) <= start_range and (txstart + %s) >= start_range
else
(txend - %s) <= end_range and (txend + %s) >= end_range
end
group by name
order by max(value) desc
)
select count(*) from (
select
max(common_name) as common_name,
name,
round(max(value), 4) as max_value,
max(chrom) as chrom,
max(strand) as strand,
max(case strand when '+' then txstart else txend end) as gene_start,
json_agg(json_build_object('value', round(value, 4), 'start', start_range, 'end', end_range)) as pred
from gene_prediction
where
gene_list = %s
and
model_name = %s
and
case strand when '+' then
(txstart - %s) <= start_range and (txstart + %s) >= start_range
else
(txend - %s) <= end_range and (txend + %s) >= end_range
end
and name in (select name from max_prediction_names)
group by name
order by max(value) desc, name
) as foo"""


class TestMaxPredictionQuery(TestCase):
    def test_max_with_guess_and_limit(self):
        expected_sql = MAX_QUERY_WITH_GUESS_WITH_LIMIT
        expected_params = ["hg38", "refgene", "E2F4", "150", "250", "250", "150", "0.4", "100", "200",
                           "refgene", "E2F4", "150", "250", "250", "150"]
        query = MaxPredictionQuery(
            schema="hg38",
            gene_list="refgene",
            model_name="E2F4",
            upstream="150",
            downstream="250",
            guess="0.4",
            limit="100",
            offset="200",
        )
        sql, params = query.get_query_and_params()
        self.assertEqual(expected_sql, sql)
        self.assertEqual(expected_params, params)

    def test_max_with_guess(self):
        expected_sql = MAX_QUERY_WITH_GUESS
        expected_params = ["hg38", "refgene", "E2F4", "150", "250", "250", "150", "0.4",
                           "refgene", "E2F4", "150", "250", "250", "150"]
        query = MaxPredictionQuery(
            schema="hg38",
            gene_list="refgene",
            model_name="E2F4",
            upstream="150",
            downstream="250",
            guess="0.4",
        )
        sql, params = query.get_query_and_params()
        self.assertEqual(expected_sql, sql)
        self.assertEqual(expected_params, params)

    def test_max_with_no_guess_and_limit(self):
        expected_sql = MAX_QUERY_NO_GUESS_WITH_LIMIT
        expected_params = ["hg38", "refgene", "E2F4", "150", "250", "250", "150", "100", "200",
                           "refgene", "E2F4", "150", "250", "250", "150"]
        query = MaxPredictionQuery(
            schema="hg38",
            gene_list="refgene",
            model_name="E2F4",
            upstream="150",
            downstream="250",
            limit="100",
            offset="200",
        )
        sql, params = query.get_query_and_params()
        self.assertEqual(expected_sql, sql)
        self.assertEqual(expected_params, params)

    def test_max_with_no_guess(self):
        expected_sql = MAX_QUERY_NO_GUESS
        expected_params = ["hg38", "refgene", "E2F4", "150", "250", "250", "150",
                           "refgene", "E2F4", "150", "250", "250", "150"]
        query = MaxPredictionQuery(
            schema="hg38",
            gene_list="refgene",
            model_name="E2F4",
            upstream="150",
            downstream="250",
        )
        sql, params = query.get_query_and_params()
        self.assertEqual(expected_sql, sql)
        self.assertEqual(expected_params, params)

    def test_max_count(self):
        expected_sql = COUNT_QUERY
        expected_params = ["hg38", "refgene", "E2F4", "150", "250", "250", "150",
                           "refgene", "E2F4", "150", "250", "250", "150"]
        query = MaxPredictionQuery(
            schema="hg38",
            gene_list="refgene",
            model_name="E2F4",
            upstream="150",
            downstream="250",
            count=True,
        )
        sql, params = query.get_query_and_params()
        self.assertEqual(expected_sql, sql)
        self.assertEqual(expected_params, params)