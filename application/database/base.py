import os
from sqlalchemy.ext.declarative import declarative_base

"""
Create a base class for all SQLAlchemy models.
All ORM models will inherit from this class to ensure they are mapped correctly to the database tables.
"""
Base = declarative_base()


def get_table_args(*args):
    """
    Helper function to conditionally add schema to table args based on environment variable.
    
    Usage:
        __table_args__ = get_table_args(
            Index("ix_name", "column"),
            UniqueConstraint("column")
        )
    
    Returns:
        tuple: Table args with schema dict if DB_SCHEMA is set, otherwise just the args
    """
    schema = os.getenv("DB_SCHEMA", "").strip()
    
    if schema:
        # If schema is set, add it to the table args
        return args + ({"schema": schema},)
    else:
        # No schema, return args as-is (or empty dict if no args)
        return args if args else ()


def get_fk_name(table_name, column_name=None):
    """
    Helper function to generate ForeignKey reference with optional schema prefix.
    
    Usage:
        ForeignKey(get_fk_name("mst_vehicles", "vehicle_id"))
    
    Returns:
        str: Table reference with schema prefix if DB_SCHEMA is set
    """
    schema = os.getenv("DB_SCHEMA", "").strip()
    
    if column_name:
        table_ref = f"{table_name}.{column_name}"
    else:
        table_ref = table_name
    
    if schema:
        return f"{schema}.{table_ref}"
    else:
        return table_ref
