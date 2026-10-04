# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Create schemas and landing volume
# MAGIC Idempotent. Creates the medallion schemas plus a managed volume that holds the raw CSVs.
# MAGIC
# MAGIC | Schema | Purpose |
# MAGIC |---|---|
# MAGIC | `aw_raw` | `landing` volume with the 72 source files, untouched |
# MAGIC | `aw_bronze` | one Delta table per file, all columns STRING, plus lineage columns |
# MAGIC | `aw_silver` | typed, cleaned, conformed tables |
# MAGIC | `aw_gold` | sales star schema and analysis marts |

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
catalog = dbutils.widgets.get("catalog")

for schema in ["aw_raw", "aw_bronze", "aw_silver", "aw_gold"]:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}`")

spark.sql(f"CREATE VOLUME IF NOT EXISTS `{catalog}`.`aw_raw`.`landing`")

display(spark.sql(f"SHOW SCHEMAS IN `{catalog}` LIKE 'aw_*'"))
