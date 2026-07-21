"""
One-time migration script: move in-memory data (pickle/JSON)
into PostgreSQL tables (entities, relations, text_segments).

Run after `python init_db.py` created the schema:
    python backend/migrations/migrate_to_postgres.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_session, init_db
from models import Entity, Relation, TextSegment
from knowledge_graph import KnowledgeGraph
from data_cleaner import DataCleaner
from vector_store import VectorStore
from config import Config


def migrate_entities(kg: KnowledgeGraph):
    """Migrate all graph nodes into Entity table."""
    with get_db_session() as db:
        existing = {e.name for e in db.query(Entity.name).all()}
        added = 0
        skipped = 0
        for node_name in kg.graph.nodes():
            if node_name in existing:
                skipped += 1
                continue
            attrs = dict(kg.graph.nodes[node_name])
            etype = attrs.pop('type', '未知')
            entity = Entity(
                name=node_name,
                entity_type=etype,
                display_name=node_name,
                address=attrs.pop('location', None),
                description=attrs.pop('description', None),
                extra_data=attrs,
            )
            db.add(entity)
            added += 1
        print(f"[Entities] Added: {added}, Skipped: {skipped}")


def migrate_relations(kg: KnowledgeGraph):
    """Migrate graph edges into Relation table."""
    with get_db_session() as db:
        name_to_id = {e.name: e.id for e in db.query(Entity).all()}
        added = 0
        skipped = 0
        for u, v, data in kg.graph.edges(data=True):
            head_id = name_to_id.get(u)
            tail_id = name_to_id.get(v)
            if not head_id or not tail_id:
                skipped += 1
                continue
            rel_type = data.get('relation', '关联')
            # Check duplicate
            dup = db.query(Relation).filter_by(
                head_entity_id=head_id, tail_entity_id=tail_id, relation_type=rel_type
            ).first()
            if dup:
                skipped += 1
                continue
            db.add(Relation(
                head_entity_id=head_id,
                tail_entity_id=tail_id,
                relation_type=rel_type,
            ))
            added += 1
        print(f"[Relations] Added: {added}, Skipped: {skipped}")


def migrate_text_segments(cleaner: DataCleaner):
    """Migrate DataCleaner text segments into TextSegment table."""
    segments = cleaner.get_all_text_segments()
    with get_db_session() as db:
        name_to_id = {e.name: e.id for e in db.query(Entity).all()}
        added = 0
        for seg in segments:
            entity_id = name_to_id.get(seg.get('name'))
            db.add(TextSegment(
                entity_id=entity_id,
                category=seg.get('category', '未知'),
                name=seg.get('name', ''),
                content=seg.get('text', ''),
            ))
            added += 1
        print(f"[TextSegments] Added: {added}")


def main():
    print("=== Migration: In-Memory -> PostgreSQL ===")
    print("Step 1: Ensure schema exists...")
    init_db()

    print("Step 2: Build knowledge graph from source data...")
    cleaner = DataCleaner()
    cleaner.load_all_data()

    kg = KnowledgeGraph()
    if not kg.load_graph():
        print("  No saved graph found, rebuilding...")
        kg.build_from_data(cleaner)

    print("Step 3: Migrate entities...")
    migrate_entities(kg)

    print("Step 4: Migrate relations...")
    migrate_relations(kg)

    print("Step 5: Migrate text segments...")
    migrate_text_segments(cleaner)

    print("=== Migration complete ===")


if __name__ == '__main__':
    main()
