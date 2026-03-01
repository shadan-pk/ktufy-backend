"""
Neo4j Service V2 - KG-RAG Corrected Version
Implements proper ontology with semantic relationships
"""
import os
import re
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def to_canonical_id(text: str, prefix: str = "") -> str:
    """Convert text to canonical snake_case ID"""
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    snake = clean.lower().strip().replace(' ', '_')
    snake = re.sub(r'_+', '_', snake).strip('_')
    return f"{prefix}_{snake}" if prefix else snake


class Neo4jServiceV2:
    """
    KG-RAG Corrected Neo4j Service
    
    Ontology:
    - Subject: Academic course
    - Module: Section within a subject
    - Concept: Atomic academic concept (formerly Topic)
    
    Relationships:
    - HAS_MODULE: Subject → Module
    - CONTAINS: Module → Concept
    - IS_A: Concept → Concept (type hierarchy)
    - PART_OF: Concept → Concept (composition)
    - PREREQUISITE_OF: Concept/Subject → Concept/Subject
    - USES: Concept → Concept (algorithms use concepts)
    - RELATED_TO: Concept → Concept (general association)
    """
    
    def __init__(self):
        self.driver = None
        self._initialize_driver()
    
    def _initialize_driver(self):
        """Initialize Neo4j driver"""
        try:
            from neo4j import GraphDatabase
            
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            username = os.getenv("NEO4J_USERNAME", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "password")
            
            self.driver = GraphDatabase.driver(uri, auth=(username, password))
            
            with self.driver.session() as session:
                session.run("RETURN 1")
            
            logger.info(f"Neo4j connected successfully to {uri}")
            
        except ImportError:
            logger.warning("neo4j driver not installed")
        except Exception as e:
            err_str = str(e)
            if "Unauthorized" in err_str or "authentication failure" in err_str:
                print(f"\u26a0\ufe0f  Neo4j V2 auth failed — check NEO4J_PASSWORD in .env (current URI: {uri})")
                logger.warning(f"Neo4j V2 authentication failed. Verify credentials in .env file.")
            else:
                print(f"\u26a0\ufe0f  Neo4j V2 unavailable: {err_str[:120]}")
                logger.error(f"Could not connect to Neo4j V2: {e}")
            self.driver = None
    
    def is_connected(self) -> bool:
        """Check if Neo4j is connected"""
        if not self.driver:
            return False
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            return True
        except:
            return False
    
    def close(self):
        """Close the driver connection"""
        if self.driver:
            self.driver.close()
    
    # ═══════════════════════════════════════════════════════════════════════
    # Schema Setup - Corrected Ontology
    # ═══════════════════════════════════════════════════════════════════════
    
    def setup_schema(self):
        """Create constraints, indexes, and relationship types"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        schema_statements = [
            # Node constraints
            "CREATE CONSTRAINT subject_unique IF NOT EXISTS FOR (s:Subject) REQUIRE (s.code, s.regulation) IS UNIQUE",
            "CREATE CONSTRAINT module_unique IF NOT EXISTS FOR (m:Module) REQUIRE m.id IS UNIQUE",
            "CREATE CONSTRAINT concept_unique IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE",
            
            # Indexes for fast lookup
            "CREATE INDEX subject_semester IF NOT EXISTS FOR (s:Subject) ON (s.semester)",
            "CREATE INDEX subject_branch IF NOT EXISTS FOR (s:Subject) ON (s.branch)",
            "CREATE INDEX subject_regulation IF NOT EXISTS FOR (s:Subject) ON (s.regulation)",
            "CREATE INDEX concept_name IF NOT EXISTS FOR (c:Concept) ON (c.name)",
            "CREATE INDEX concept_type IF NOT EXISTS FOR (c:Concept) ON (c.concept_type)",
            "CREATE INDEX module_subject IF NOT EXISTS FOR (m:Module) ON (m.subject_code)",
            
            # Full-text search indexes
            "CREATE FULLTEXT INDEX concept_search IF NOT EXISTS FOR (c:Concept) ON EACH [c.name, c.display_name]",
        ]
        
        with self.driver.session() as session:
            for stmt in schema_statements:
                try:
                    session.run(stmt)
                    logger.info(f"Executed: {stmt[:60]}...")
                except Exception as e:
                    # Index might already exist
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Schema statement warning: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # Load Syllabus Data (New V2 Format)
    # ═══════════════════════════════════════════════════════════════════════
    
    def load_syllabus_data(self, syllabus_data: dict) -> dict:
        """
        Load complete syllabus data from V2 extractor
        
        Args:
            syllabus_data: Output from LLMExtractorV2.extract_syllabus_structure()
            
        Returns:
            Statistics about loaded data
        """
        stats = {
            "subjects_created": 0,
            "modules_created": 0,
            "concepts_created": 0,
            "relationships_created": 0,
            "errors": []
        }
        
        semester = syllabus_data.get("semester", 0)
        branch = syllabus_data.get("branch", "")
        regulation = syllabus_data.get("regulation", "2019")
        
        # 1. Create subjects and modules
        for subject in syllabus_data.get("subjects", []):
            try:
                self.create_subject(subject, semester, branch, regulation)
                stats["subjects_created"] += 1
                
                for module in subject.get("modules", []):
                    self.create_module(module, subject["code"], regulation)
                    stats["modules_created"] += 1
                    
                    # Create concepts from atomic topics
                    for topic in module.get("topics", []):
                        self.create_concept(topic, module["id"])
                        stats["concepts_created"] += 1
                        
            except Exception as e:
                stats["errors"].append(f"Subject {subject.get('code')}: {str(e)}")
        
        # 2. Create semantic relationships
        for rel in syllabus_data.get("relationships", []):
            try:
                self.create_semantic_relationship(
                    from_id=rel["from_id"],
                    to_id=rel["to_id"],
                    rel_type=rel["type"],
                    properties={"confidence": rel.get("confidence", 0.5)}
                )
                stats["relationships_created"] += 1
            except Exception as e:
                stats["errors"].append(f"Relationship {rel.get('from_id')} → {rel.get('to_id')}: {str(e)}")
        
        return stats
    
    # ═══════════════════════════════════════════════════════════════════════
    # Subject Operations
    # ═══════════════════════════════════════════════════════════════════════
    
    def create_subject(
        self, 
        subject_data: dict, 
        semester: int, 
        branch: str, 
        regulation: str
    ) -> dict:
        """Create a subject node"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MERGE (s:Subject {code: $code, regulation: $regulation})
        SET s.id = $id,
            s.name = $name,
            s.display_name = $display_name,
            s.credits = $credits,
            s.category = $category,
            s.semester = $semester,
            s.branch = $branch,
            s.hours_per_week = $hours_per_week,
            s.textbooks = $textbooks,
            s.course_outcomes = $course_outcomes,
            s.updated_at = datetime()
        RETURN s
        """
        
        subject_id = to_canonical_id(subject_data["name"], subject_data["code"].lower())
        
        with self.driver.session() as session:
            result = session.run(
                query,
                code=subject_data["code"],
                regulation=regulation,
                id=subject_id,
                name=subject_data["name"],
                display_name=subject_data["name"],
                credits=subject_data.get("credits", 0),
                category=subject_data.get("category", ""),
                semester=semester,
                branch=branch,
                hours_per_week=subject_data.get("hours_per_week", 0),
                textbooks=subject_data.get("textbooks", []),
                course_outcomes=subject_data.get("course_outcomes", [])
            )
            record = result.single()
            return dict(record["s"]) if record else None
    
    def get_subject(self, code: str, regulation: str = "2019") -> Optional[dict]:
        """Get subject with all its data"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH (s:Subject {code: $code, regulation: $regulation})
        OPTIONAL MATCH (s)-[:HAS_MODULE]->(m:Module)
        OPTIONAL MATCH (m)-[:CONTAINS]->(c)
        WITH s, m, collect(DISTINCT c) as concepts
        ORDER BY m.number
        WITH s, collect({module: m, concepts: concepts}) as modules_data
        RETURN s, modules_data
        """
        
        with self.driver.session() as session:
            result = session.run(query, code=code, regulation=regulation)
            record = result.single()
            
            if not record:
                return None
            
            subject = dict(record["s"])
            subject["modules"] = []
            
            for md in record["modules_data"]:
                if md["module"]:
                    module = dict(md["module"])
                    module["concepts"] = [dict(c) for c in md["concepts"]]
                    subject["modules"].append(module)
            
            return subject
    
    def get_all_subjects(
        self, 
        semester: Optional[int] = None, 
        branch: Optional[str] = None,
        regulation: Optional[str] = None
    ) -> List[dict]:
        """Get all subjects with filters"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        conditions = []
        params = {}
        
        if semester:
            conditions.append("s.semester = $semester")
            params["semester"] = semester
        if branch:
            conditions.append("s.branch = $branch")
            params["branch"] = branch
        if regulation:
            conditions.append("s.regulation = $regulation")
            params["regulation"] = regulation
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        query = f"""
        MATCH (s:Subject)
        {where_clause}
        OPTIONAL MATCH (s)-[:HAS_MODULE]->(m:Module)
        OPTIONAL MATCH (m)-[:CONTAINS]->(c)
        RETURN s, count(DISTINCT m) as module_count, count(DISTINCT c) as concept_count
        ORDER BY s.semester, s.code
        """
        
        with self.driver.session() as session:
            result = session.run(query, **params)
            subjects = []
            for record in result:
                subject = dict(record["s"])
                subject["module_count"] = record["module_count"]
                subject["concept_count"] = record["concept_count"]
                subjects.append(subject)
            return subjects
    
    # ═══════════════════════════════════════════════════════════════════════
    # Module Operations
    # ═══════════════════════════════════════════════════════════════════════
    
    def create_module(self, module_data: dict, subject_code: str, regulation: str = "2019") -> dict:
        """Create a module and link to subject"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        module_id = module_data.get("id", f"{subject_code.lower()}_m{module_data['number']}")
        
        query = """
        MATCH (s:Subject {code: $subject_code, regulation: $regulation})
        MERGE (m:Module {id: $module_id})
        SET m.name = $name,
            m.display_name = $display_name,
            m.number = $number,
            m.hours = $hours,
            m.subject_code = $subject_code,
            m.syllabus_text = $syllabus_text,
            m.updated_at = datetime()
        MERGE (s)-[:HAS_MODULE]->(m)
        RETURN m
        """
        
        with self.driver.session() as session:
            result = session.run(
                query,
                subject_code=subject_code,
                regulation=regulation,
                module_id=module_id,
                name=module_data.get("name", f"Module {module_data['number']}"),
                display_name=module_data.get("name", f"Module {module_data['number']}"),
                number=module_data["number"],
                hours=module_data.get("hours", 0),
                syllabus_text=module_data.get("syllabus_text", "")
            )
            record = result.single()
            return dict(record["m"]) if record else None
    
    def get_modules(self, subject_code: str, regulation: str = "2019") -> List[dict]:
        """Get all modules for a subject"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH (s:Subject {code: $code, regulation: $regulation})-[:HAS_MODULE]->(m:Module)
        OPTIONAL MATCH (m)-[:CONTAINS]->(c)
        RETURN m, collect(c) as concepts
        ORDER BY m.number
        """
        
        with self.driver.session() as session:
            result = session.run(query, code=subject_code, regulation=regulation)
            modules = []
            for record in result:
                module = dict(record["m"])
                module["concepts"] = [dict(c) for c in record["concepts"]]
                modules.append(module)
            return modules
    
    # ═══════════════════════════════════════════════════════════════════════
    # Concept Operations (Atomic Topics)
    # ═══════════════════════════════════════════════════════════════════════
    
    def create_concept(self, concept_data: dict, module_id: str) -> dict:
        """Create an atomic concept node and link to module"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        concept_id = concept_data.get("id", to_canonical_id(concept_data["name"], module_id))
        
        query = """
        MATCH (m:Module {id: $module_id})
        MERGE (c:Concept {id: $concept_id})
        SET c.name = $name,
            c.display_name = $display_name,
            c.original_text = $original_text,
            c.module_id = $module_id,
            c.subject_code = $subject_code,
            c.concept_type = $concept_type,
            c.updated_at = datetime()
        MERGE (m)-[:CONTAINS]->(c)
        RETURN c
        """
        
        with self.driver.session() as session:
            result = session.run(
                query,
                module_id=module_id,
                concept_id=concept_id,
                name=concept_data.get("name", ""),
                display_name=concept_data.get("display_name", concept_data.get("name", "")),
                original_text=concept_data.get("original_text", ""),
                subject_code=concept_data.get("subject_code", ""),
                concept_type=concept_data.get("concept_type", "topic")
            )
            record = result.single()
            return dict(record["c"]) if record else None
    
    def get_concept(self, concept_id: str) -> Optional[dict]:
        """Get a concept with its relationships"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH (c:Concept {id: $id})
        OPTIONAL MATCH (c)-[r]->(related:Concept)
        OPTIONAL MATCH (c)<-[:CONTAINS]-(m:Module)<-[:HAS_MODULE]-(s:Subject)
        RETURN c, 
               collect(DISTINCT {type: type(r), concept: related}) as outgoing,
               m, s
        """
        
        with self.driver.session() as session:
            result = session.run(query, id=concept_id)
            record = result.single()
            
            if not record:
                return None
            
            concept = dict(record["c"])
            concept["module"] = dict(record["m"]) if record["m"] else None
            concept["subject"] = dict(record["s"]) if record["s"] else None
            concept["relationships"] = [
                {"type": r["type"], "concept": dict(r["concept"])} 
                for r in record["outgoing"] if r["concept"]
            ]
            return concept
    
    def search_concepts(self, query: str, limit: int = 20) -> List[dict]:
        """Full-text search for concepts"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        # Try full-text search first
        cypher = """
        CALL db.index.fulltext.queryNodes('concept_search', $query) 
        YIELD node, score
        MATCH (m:Module)-[:CONTAINS]->(node)
        MATCH (s:Subject)-[:HAS_MODULE]->(m)
        RETURN node as c, m, s, score
        ORDER BY score DESC
        LIMIT $limit
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(cypher, query=f"*{query}*", limit=limit)
                concepts = []
                for record in result:
                    concept = dict(record["c"])
                    concept["module"] = dict(record["m"])
                    concept["subject"] = dict(record["s"])
                    concept["score"] = record["score"]
                    concepts.append(concept)
                return concepts
        except:
            # Fallback to CONTAINS search
            return self._search_concepts_fallback(query, limit)
    
    def _search_concepts_fallback(self, query: str, limit: int) -> List[dict]:
        """Fallback search using CONTAINS"""
        cypher = """
        MATCH (c:Concept)
        WHERE toLower(c.name) CONTAINS toLower($query)
           OR toLower(c.display_name) CONTAINS toLower($query)
        MATCH (m:Module)-[:CONTAINS]->(c)
        MATCH (s:Subject)-[:HAS_MODULE]->(m)
        RETURN c, m, s
        LIMIT $limit
        """
        
        with self.driver.session() as session:
            result = session.run(cypher, query=query, limit=limit)
            concepts = []
            for record in result:
                concept = dict(record["c"])
                concept["module"] = dict(record["m"])
                concept["subject"] = dict(record["s"])
                concepts.append(concept)
            return concepts
    
    # ═══════════════════════════════════════════════════════════════════════
    # Semantic Relationships
    # ═══════════════════════════════════════════════════════════════════════
    
    def create_semantic_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        properties: dict = None
    ) -> bool:
        """
        Create a semantic relationship between concepts
        
        Supported types:
        - IS_A: Type hierarchy (binary_tree IS_A tree)
        - PART_OF: Composition (node PART_OF linked_list)
        - PREREQUISITE_OF: Learning dependency
        - USES: Algorithm uses concept
        - IMPLEMENTS: Implementation relationship
        - RELATED_TO: General association
        """
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        valid_types = ["IS_A", "PART_OF", "PREREQUISITE_OF", "USES", "IMPLEMENTS", "RELATED_TO"]
        if rel_type not in valid_types:
            rel_type = "RELATED_TO"
        
        props = properties or {}
        props_str = ", ".join([f"r.{k} = ${k}" for k in props.keys()])
        set_clause = f"SET {props_str}" if props_str else ""
        
        query = f"""
        MATCH (from:Concept {{id: $from_id}})
        MATCH (to:Concept {{id: $to_id}})
        MERGE (from)-[r:{rel_type}]->(to)
        {set_clause}
        SET r.created_at = datetime()
        RETURN r
        """
        
        with self.driver.session() as session:
            result = session.run(query, from_id=from_id, to_id=to_id, **props)
            return result.single() is not None
    
    def create_subject_prerequisite(
        self,
        from_code: str,
        to_code: str,
        regulation: str = "2019",
        reason: str = ""
    ) -> bool:
        """Create prerequisite relationship between subjects"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH (prereq:Subject {code: $from_code, regulation: $regulation})
        MATCH (subject:Subject {code: $to_code, regulation: $regulation})
        MERGE (prereq)-[r:PREREQUISITE_OF]->(subject)
        SET r.reason = $reason, r.created_at = datetime()
        RETURN r
        """
        
        with self.driver.session() as session:
            result = session.run(
                query, 
                from_code=from_code, 
                to_code=to_code, 
                regulation=regulation,
                reason=reason
            )
            return result.single() is not None
    
    # ═══════════════════════════════════════════════════════════════════════
    # Graph Queries (for KG-RAG)
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_prerequisites(self, concept_id: str, depth: int = 3) -> List[dict]:
        """Get all prerequisites for a concept (traverses PREREQUISITE_OF)"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH path = (prereq:Concept)-[:PREREQUISITE_OF*1..$depth]->(c:Concept {id: $id})
        RETURN prereq, length(path) as distance
        ORDER BY distance
        """
        
        with self.driver.session() as session:
            result = session.run(query, id=concept_id, depth=depth)
            return [
                {"concept": dict(record["prereq"]), "distance": record["distance"]}
                for record in result
            ]
    
    def get_type_hierarchy(self, concept_id: str) -> dict:
        """Get IS_A hierarchy for a concept"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH (c:Concept {id: $id})
        OPTIONAL MATCH path_up = (c)-[:IS_A*1..5]->(parent:Concept)
        OPTIONAL MATCH path_down = (child:Concept)-[:IS_A*1..5]->(c)
        RETURN c,
               collect(DISTINCT parent) as parents,
               collect(DISTINCT child) as children
        """
        
        with self.driver.session() as session:
            result = session.run(query, id=concept_id)
            record = result.single()
            
            if not record:
                return None
            
            return {
                "concept": dict(record["c"]),
                "parents": [dict(p) for p in record["parents"]],
                "children": [dict(ch) for ch in record["children"]]
            }
    
    def get_related_concepts(self, concept_id: str, rel_types: List[str] = None) -> List[dict]:
        """Get concepts related to a given concept"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        if rel_types:
            type_filter = f"[:{' | '.join(rel_types)}]"
        else:
            type_filter = ""
        
        query = f"""
        MATCH (c:Concept {{id: $id}})-{type_filter}-(related:Concept)
        RETURN DISTINCT related, 
               [(c)-[r]-(related) | type(r)] as relationship_types
        LIMIT 50
        """
        
        with self.driver.session() as session:
            result = session.run(query, id=concept_id)
            return [
                {
                    "concept": dict(record["related"]),
                    "relationship_types": list(set(record["relationship_types"]))
                }
                for record in result
            ]
    
    def get_learning_path(self, from_concept_id: str, to_concept_id: str) -> List[dict]:
        """Find learning path between two concepts"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH path = shortestPath(
            (start:Concept {id: $from_id})-[:PREREQUISITE_OF|IS_A|PART_OF*1..10]->(end:Concept {id: $to_id})
        )
        RETURN nodes(path) as concepts, relationships(path) as rels
        """
        
        with self.driver.session() as session:
            result = session.run(query, from_id=from_concept_id, to_id=to_concept_id)
            record = result.single()
            
            if not record:
                return []
            
            path = []
            concepts = record["concepts"]
            rels = record["rels"]
            
            for i, concept in enumerate(concepts):
                step = {"concept": dict(concept)}
                if i < len(rels):
                    step["next_relationship"] = rels[i].type
                path.append(step)
            
            return path
    
    # ═══════════════════════════════════════════════════════════════════════
    # Statistics
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_statistics(self) -> dict:
        """Get comprehensive graph statistics"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH (s:Subject) WITH count(s) as subjects
        OPTIONAL MATCH (m:Module) WITH subjects, count(m) as modules
        OPTIONAL MATCH (c:Concept) WITH subjects, modules, count(c) as concepts
        MATCH ()-[r]->() WITH subjects, modules, concepts, count(r) as relationships
        MATCH (sub:Subject) WITH subjects, modules, concepts, relationships, 
              collect(DISTINCT sub.branch) as branches,
              collect(DISTINCT sub.semester) as semesters,
              collect(DISTINCT sub.regulation) as regulations
        RETURN subjects, modules, concepts, relationships, branches, semesters, regulations
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            record = result.single()
            
            if not record:
                return {
                    "total_subjects": 0,
                    "total_modules": 0,
                    "total_concepts": 0,
                    "total_relationships": 0,
                    "branches": [],
                    "semesters": [],
                    "regulations": []
                }
            
            return {
                "total_subjects": record["subjects"],
                "total_modules": record["modules"],
                "total_concepts": record["concepts"],
                "total_relationships": record["relationships"],
                "branches": [b for b in record["branches"] if b],
                "semesters": sorted([s for s in record["semesters"] if s]),
                "regulations": [r for r in record["regulations"] if r]
            }
    
    # ═══════════════════════════════════════════════════════════════════════
    # Cleanup
    # ═══════════════════════════════════════════════════════════════════════
    
    def delete_subject(self, code: str, regulation: str = "2019") -> bool:
        """Delete a subject and all its modules/concepts"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH (s:Subject {code: $code, regulation: $regulation})
        OPTIONAL MATCH (s)-[:HAS_MODULE]->(m:Module)
        OPTIONAL MATCH (m)-[:CONTAINS]->(c)
        DETACH DELETE s, m, c
        RETURN count(s) as deleted
        """
        
        with self.driver.session() as session:
            result = session.run(query, code=code, regulation=regulation)
            record = result.single()
            return record["deleted"] > 0 if record else False
    
    def clear_all(self) -> dict:
        """Clear all data (use with caution!)"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH (n)
        DETACH DELETE n
        RETURN count(n) as deleted
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            record = result.single()
            return {"deleted_nodes": record["deleted"] if record else 0}


# Global instance
neo4j_service = Neo4jServiceV2()
