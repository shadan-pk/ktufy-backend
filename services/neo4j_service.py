"""
Neo4j Service
Manages Knowledge Graph operations in Neo4j
"""
import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class Neo4jService:
    """
    Neo4j Knowledge Graph management service
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
            
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            
            logger.info(f"Neo4j connected successfully to {uri}")
            
        except ImportError:
            logger.warning("neo4j driver not installed. Install with: pip install neo4j")
        except Exception as e:
            err_str = str(e)
            if "Unauthorized" in err_str or "authentication failure" in err_str:
                print(f"\u26a0\ufe0f  Neo4j auth failed — check NEO4J_PASSWORD in .env (current URI: {uri})")
                logger.warning(f"Neo4j authentication failed. Verify credentials in .env file.")
            else:
                print(f"\u26a0\ufe0f  Neo4j unavailable: {err_str[:120]}")
                logger.error(f"Could not connect to Neo4j: {e}")
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
    # Schema Setup
    # ═══════════════════════════════════════════════════════════════════════
    
    def setup_constraints(self):
        """Create database constraints and indexes"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        constraints = [
            # Composite unique constraint: same subject code can exist in different regulations
            "CREATE CONSTRAINT subject_code_regulation IF NOT EXISTS FOR (s:Subject) REQUIRE (s.code, s.regulation) IS UNIQUE",
            "CREATE CONSTRAINT module_id IF NOT EXISTS FOR (m:Module) REQUIRE m.id IS UNIQUE",
            "CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE",
            "CREATE INDEX subject_semester IF NOT EXISTS FOR (s:Subject) ON (s.semester)",
            "CREATE INDEX subject_branch IF NOT EXISTS FOR (s:Subject) ON (s.branch)",
            "CREATE INDEX subject_regulation IF NOT EXISTS FOR (s:Subject) ON (s.regulation)",
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.info(f"Executed: {constraint[:50]}...")
                except Exception as e:
                    logger.warning(f"Constraint may already exist: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # Subject Operations
    # ═══════════════════════════════════════════════════════════════════════
    
    def create_subject(self, subject_data: dict) -> dict:
        """
        Create a subject node in the knowledge graph
        
        Args:
            subject_data: Subject information
            
        Returns:
            Created subject data
        """
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MERGE (s:Subject {code: $code, regulation: $regulation})
        SET s.name = $name,
            s.credits = $credits,
            s.category = $category,
            s.semester = $semester,
            s.branch = $branch,
            s.regulation = $regulation,
            s.textbooks = $textbooks,
            s.objectives = $objectives,
            s.updated_at = datetime()
        RETURN s
        """
        
        with self.driver.session() as session:
            result = session.run(
                query,
                code=subject_data["code"],
                name=subject_data["name"],
                credits=subject_data.get("credits", 0),
                category=subject_data.get("category", ""),
                semester=subject_data.get("semester", 0),
                branch=subject_data.get("branch", ""),
                regulation=subject_data.get("regulation", "2019"),
                textbooks=subject_data.get("textbooks", []),
                objectives=subject_data.get("objectives", [])
            )
            record = result.single()
            return dict(record["s"]) if record else None
    
    def get_subject(self, code: str) -> Optional[dict]:
        """Get a subject by code"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH (s:Subject {code: $code})
        OPTIONAL MATCH (s)-[:HAS_MODULE]->(m:Module)
        OPTIONAL MATCH (m)-[:CONTAINS]->(t:Topic)
        RETURN s, collect(DISTINCT m) as modules, collect(DISTINCT t) as topics
        """
        
        with self.driver.session() as session:
            result = session.run(query, code=code)
            record = result.single()
            
            if not record:
                return None
            
            subject = dict(record["s"])
            subject["modules"] = [dict(m) for m in record["modules"]]
            subject["topics"] = [dict(t) for t in record["topics"]]
            return subject
    
    def get_all_subjects(
        self, 
        semester: Optional[int] = None, 
        branch: Optional[str] = None,
        regulation: Optional[str] = None
    ) -> List[dict]:
        """Get all subjects, optionally filtered by semester, branch, and regulation"""
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
        RETURN s, count(m) as module_count
        ORDER BY s.semester, s.code
        """
        
        with self.driver.session() as session:
            result = session.run(query, **params)
            subjects = []
            for record in result:
                subject = dict(record["s"])
                subject["module_count"] = record["module_count"]
                subjects.append(subject)
            return subjects
    
    def delete_subject(self, code: str) -> bool:
        """Delete a subject and all its modules/topics"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH (s:Subject {code: $code})
        OPTIONAL MATCH (s)-[:HAS_MODULE]->(m:Module)
        OPTIONAL MATCH (m)-[:CONTAINS]->(t:Topic)
        DETACH DELETE s, m, t
        RETURN count(s) as deleted
        """
        
        with self.driver.session() as session:
            result = session.run(query, code=code)
            record = result.single()
            return record["deleted"] > 0 if record else False
    
    # ═══════════════════════════════════════════════════════════════════════
    # Module Operations
    # ═══════════════════════════════════════════════════════════════════════
    
    def create_module(self, module_data: dict, subject_code: str) -> dict:
        """Create a module and link to subject"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        module_id = f"{subject_code}_M{module_data['number']}"
        
        query = """
        MATCH (s:Subject {code: $subject_code})
        MERGE (m:Module {id: $module_id})
        SET m.name = $name,
            m.number = $number,
            m.hours = $hours,
            m.subject_code = $subject_code
        MERGE (s)-[:HAS_MODULE]->(m)
        RETURN m
        """
        
        with self.driver.session() as session:
            result = session.run(
                query,
                subject_code=subject_code,
                module_id=module_id,
                name=module_data.get("name", f"Module {module_data['number']}"),
                number=module_data["number"],
                hours=module_data.get("hours", 0)
            )
            record = result.single()
            return dict(record["m"]) if record else None
    
    def get_modules(self, subject_code: str) -> List[dict]:
        """Get all modules for a subject"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH (s:Subject {code: $code})-[:HAS_MODULE]->(m:Module)
        OPTIONAL MATCH (m)-[:CONTAINS]->(t:Topic)
        RETURN m, collect(t) as topics
        ORDER BY m.number
        """
        
        with self.driver.session() as session:
            result = session.run(query, code=subject_code)
            modules = []
            for record in result:
                module = dict(record["m"])
                module["topics"] = [dict(t) for t in record["topics"]]
                modules.append(module)
            return modules
    
    # ═══════════════════════════════════════════════════════════════════════
    # Topic Operations
    # ═══════════════════════════════════════════════════════════════════════
    
    def create_topic(self, topic_data: dict, module_id: str) -> dict:
        """Create a topic and link to module"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        # Generate topic ID
        topic_name_slug = topic_data["name"][:30].replace(" ", "_").replace("/", "_")
        topic_id = f"{module_id}_{topic_name_slug}"
        
        query = """
        MATCH (m:Module {id: $module_id})
        MERGE (t:Topic {id: $topic_id})
        SET t.name = $name,
            t.description = $description,
            t.keywords = $keywords,
            t.module_id = $module_id
        MERGE (m)-[:CONTAINS]->(t)
        RETURN t
        """
        
        with self.driver.session() as session:
            result = session.run(
                query,
                module_id=module_id,
                topic_id=topic_id,
                name=topic_data["name"],
                description=topic_data.get("description", ""),
                keywords=topic_data.get("keywords", [])
            )
            record = result.single()
            return dict(record["t"]) if record else None
    
    def search_topics(self, query: str, limit: int = 10) -> List[dict]:
        """Search topics by name or keywords"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        cypher = """
        MATCH (t:Topic)
        WHERE toLower(t.name) CONTAINS toLower($query)
           OR any(k IN t.keywords WHERE toLower(k) CONTAINS toLower($query))
        MATCH (m:Module)-[:CONTAINS]->(t)
        MATCH (s:Subject)-[:HAS_MODULE]->(m)
        RETURN t, m, s
        LIMIT $limit
        """
        
        with self.driver.session() as session:
            result = session.run(cypher, query=query, limit=limit)
            topics = []
            for record in result:
                topic = dict(record["t"])
                topic["module"] = dict(record["m"])
                topic["subject"] = dict(record["s"])
                topics.append(topic)
            return topics
    
    def search_concepts(self, query: str, limit: int = 10) -> List[dict]:
        """
        Search concepts across the knowledge graph (topics, modules, subjects).
        Returns results with canonical_id for relationship lookups.
        """
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        # Extract meaningful keywords from the query
        stop_words = {'explain', 'what', 'is', 'are', 'the', 'a', 'an', 'of', 'in', 'to', 'for', 'how', 'why', 'can', 'you', 'me', 'about', 'ktu', 'tell'}
        words = query.lower().split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        print(f"      🔎 Neo4j searching for keywords: {keywords}")
        
        # First check if we have any data at all
        with self.driver.session() as session:
            count_result = session.run("""
                MATCH (t:Topic) WITH count(t) as topics
                MATCH (m:Module) WITH topics, count(m) as modules  
                MATCH (s:Subject) WITH topics, modules, count(s) as subjects
                RETURN topics, modules, subjects
            """)
            counts = count_result.single()
            if counts:
                print(f"      📊 Neo4j data: {counts['topics']} topics, {counts['modules']} modules, {counts['subjects']} subjects")
        
        # Search across Topic, Module, and Subject nodes using keywords
        # Simplified query to avoid nested aggregation issues
        cypher = """
        // Search Topics with their parent module and subject
        OPTIONAL MATCH (t:Topic)
        WHERE any(kw IN $keywords WHERE toLower(t.name) CONTAINS kw)
           OR any(kw IN $keywords WHERE any(k IN t.keywords WHERE toLower(k) CONTAINS kw))
        OPTIONAL MATCH (m:Module)-[:CONTAINS]->(t)
        OPTIONAL MATCH (s:Subject)-[:HAS_MODULE]->(m)
        WITH collect(DISTINCT {
            canonical_id: t.id,
            name: t.name,
            type: 'Topic',
            description: t.description,
            keywords: t.keywords,
            module_name: m.name,
            module_number: m.number,
            subject_name: s.name,
            subject_code: s.code
        }) as topics
        
        // Search Modules with their parent subject
        OPTIONAL MATCH (m2:Module)
        WHERE any(kw IN $keywords WHERE toLower(m2.name) CONTAINS kw)
           OR any(kw IN $keywords WHERE toLower(coalesce(m2.description, '')) CONTAINS kw)
           OR any(kw IN $keywords WHERE kw =~ '\\\\d+' AND m2.number = toInteger(kw))
        OPTIONAL MATCH (s2:Subject)-[:HAS_MODULE]->(m2)
        WITH topics, collect(DISTINCT {
            canonical_id: m2.id,
            name: m2.name,
            type: 'Module',
            description: m2.description,
            module_number: m2.number,
            subject_name: s2.name,
            subject_code: s2.code
        }) as modules
        
        // Search Subjects
        OPTIONAL MATCH (s3:Subject)
        WHERE any(kw IN $keywords WHERE toLower(s3.name) CONTAINS kw)
           OR any(kw IN $keywords WHERE toLower(s3.code) CONTAINS kw)
        WITH topics, modules, collect(DISTINCT {
            canonical_id: s3.code,
            name: s3.name,
            type: 'Subject',
            description: coalesce(s3.description, ''),
            subject_code: s3.code
        }) as subjects
        
        // Combine all results
        RETURN topics + modules + subjects as results
        """
        
        with self.driver.session() as session:
            result = session.run(cypher, keywords=keywords)
            record = result.single()
            if record:
                # Filter out null results and limit
                results = [r for r in record["results"] if r.get("canonical_id")]
                print(f"      ✅ Found {len(results)} concepts")
                return results[:limit]
            return []
    
    def get_concept_relationships(self, concept_id: str) -> List[dict]:
        """
        Get all relationships for a concept (topic, module, or subject).
        Returns related concepts with relationship type.
        """
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        cypher = """
        // Try to find the node by ID across different node types
        OPTIONAL MATCH (t:Topic {id: $concept_id})
        OPTIONAL MATCH (m:Module {id: $concept_id})
        OPTIONAL MATCH (s:Subject {code: $concept_id})
        
        WITH coalesce(t, m, s) as node
        WHERE node IS NOT NULL
        
        // Get all outgoing relationships
        OPTIONAL MATCH (node)-[r]->(related)
        WHERE related:Topic OR related:Module OR related:Subject
        
        WITH collect({
            related_id: coalesce(related.id, related.code),
            related_name: related.name,
            related_type: labels(related)[0],
            relationship: type(r),
            direction: 'outgoing'
        }) as outgoing
        
        // Get all incoming relationships
        OPTIONAL MATCH (node)<-[r]-(related)
        WHERE related:Topic OR related:Module OR related:Subject
        
        WITH outgoing, collect({
            related_id: coalesce(related.id, related.code),
            related_name: related.name,
            related_type: labels(related)[0],
            relationship: type(r),
            direction: 'incoming'
        }) as incoming
        
        RETURN outgoing + incoming as relationships
        """
        
        with self.driver.session() as session:
            result = session.run(cypher, concept_id=concept_id)
            record = result.single()
            if record:
                # Filter out null relationships
                relationships = [r for r in record["relationships"] if r.get("related_id")]
                return relationships
            return []
    
    def get_topic_prerequisites(self, topic_id: str) -> List[dict]:
        """
        Get prerequisites for a topic (concepts that should be learned first).
        Falls back to module/subject prerequisites if topic-level not found.
        """
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        cypher = """
        // Find the topic
        MATCH (t:Topic {id: $topic_id})
        
        // Get the module and subject for context
        OPTIONAL MATCH (m:Module)-[:CONTAINS]->(t)
        OPTIONAL MATCH (s:Subject)-[:HAS_MODULE]->(m)
        
        // Look for direct topic prerequisites
        OPTIONAL MATCH (prereq_topic:Topic)-[:PREREQUISITE_OF]->(t)
        
        // Look for subject prerequisites
        OPTIONAL MATCH (prereq_subject:Subject)-[:PREREQUISITE_OF]->(s)
        
        WITH collect(DISTINCT {
            id: prereq_topic.id,
            name: prereq_topic.name,
            type: 'Topic',
            reason: null
        }) as topic_prereqs,
        collect(DISTINCT {
            id: prereq_subject.code,
            name: prereq_subject.name,
            type: 'Subject',
            reason: null
        }) as subject_prereqs
        
        RETURN topic_prereqs + subject_prereqs as prerequisites
        """
        
        with self.driver.session() as session:
            result = session.run(cypher, topic_id=topic_id)
            record = result.single()
            if record:
                prereqs = [p for p in record["prerequisites"] if p.get("id")]
                return prereqs
            return []
    
    # ═══════════════════════════════════════════════════════════════════════
    # Relationship Operations
    # ═══════════════════════════════════════════════════════════════════════
    
    def create_prerequisite(self, from_code: str, to_code: str, reason: str = "") -> bool:
        """Create a prerequisite relationship between subjects"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH (s1:Subject {code: $from_code})
        MATCH (s2:Subject {code: $to_code})
        MERGE (s1)-[r:PREREQUISITE_OF]->(s2)
        SET r.reason = $reason
        RETURN r
        """
        
        with self.driver.session() as session:
            result = session.run(query, from_code=from_code, to_code=to_code, reason=reason)
            return result.single() is not None
    
    def create_topic_relationship(
        self, 
        from_topic_id: str, 
        to_topic_id: str, 
        relationship: str = "RELATED_TO"
    ) -> bool:
        """Create a relationship between topics"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = f"""
        MATCH (t1:Topic {{id: $from_id}})
        MATCH (t2:Topic {{id: $to_id}})
        MERGE (t1)-[r:{relationship}]->(t2)
        RETURN r
        """
        
        with self.driver.session() as session:
            result = session.run(query, from_id=from_topic_id, to_id=to_topic_id)
            return result.single() is not None
    
    def get_related_topics(self, topic_id: str, depth: int = 2) -> List[dict]:
        """Get topics related to a given topic"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH (t:Topic {id: $topic_id})-[r*1..$depth]-(related:Topic)
        RETURN DISTINCT related
        LIMIT 20
        """
        
        with self.driver.session() as session:
            result = session.run(query, topic_id=topic_id, depth=depth)
            return [dict(record["related"]) for record in result]
    
    def get_prerequisites(self, subject_code: str) -> List[dict]:
        """Get prerequisite subjects for a given subject"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = """
        MATCH (prereq:Subject)-[r:PREREQUISITE_OF]->(s:Subject {code: $code})
        RETURN prereq, r.reason as reason
        """
        
        with self.driver.session() as session:
            result = session.run(query, code=subject_code)
            prereqs = []
            for record in result:
                prereq = dict(record["prereq"])
                prereq["reason"] = record["reason"]
                prereqs.append(prereq)
            return prereqs
    
    # ═══════════════════════════════════════════════════════════════════════
    # Statistics
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_statistics(self) -> dict:
        """Get knowledge graph statistics"""
        if not self.driver:
            return {
                "connected": False,
                "total_subjects": 0,
                "total_modules": 0,
                "total_topics": 0,
                "total_relationships": 0,
                "branches": [],
                "semesters": [],
                "regulations": []
            }
        
        query = """
        MATCH (s:Subject) WITH count(s) as subjects
        MATCH (m:Module) WITH subjects, count(m) as modules
        MATCH (t:Topic) WITH subjects, modules, count(t) as topics
        MATCH ()-[r]->() WITH subjects, modules, topics, count(r) as rels
        MATCH (s2:Subject) WITH subjects, modules, topics, rels, 
              collect(DISTINCT s2.branch) as branches,
              collect(DISTINCT s2.semester) as semesters,
              collect(DISTINCT s2.regulation) as regulations
        RETURN subjects, modules, topics, rels, branches, semesters, regulations
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query)
                record = result.single()
                
                if record:
                    return {
                        "connected": True,
                        "total_subjects": record["subjects"],
                        "total_modules": record["modules"],
                        "total_topics": record["topics"],
                        "total_relationships": record["rels"],
                        "branches": [b for b in record["branches"] if b],
                        "semesters": sorted([s for s in record["semesters"] if s]),
                        "regulations": sorted([r for r in record["regulations"] if r])
                    }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
        
        return {
            "connected": True,
            "total_subjects": 0,
            "total_modules": 0,
            "total_topics": 0,
            "total_relationships": 0,
            "branches": [],
            "semesters": [],
            "regulations": []
        }
    
    # ═══════════════════════════════════════════════════════════════════════
    # Bulk Operations
    # ═══════════════════════════════════════════════════════════════════════
    
    def load_syllabus_data(self, data: dict) -> dict:
        """
        Load complete syllabus data into the knowledge graph
        
        Args:
            data: Structured syllabus data with subjects, modules, topics
            
        Returns:
            Statistics about loaded data
        """
        stats = {
            "subjects_created": 0,
            "modules_created": 0,
            "topics_created": 0,
            "errors": []
        }
        
        for subject in data.get("subjects", []):
            try:
                # Validate subject has required fields
                subject_code = subject.get("code")
                if not subject_code:
                    error_msg = f"Skipping subject with missing code: {subject.get('name', 'unknown')}"
                    logger.warning(error_msg)
                    stats["errors"].append(error_msg)
                    continue
                
                # Add semester and branch from parent
                subject["semester"] = data.get("semester", subject.get("semester", 0))
                subject["branch"] = data.get("branch", subject.get("branch", ""))
                
                # Create subject
                self.create_subject(subject)
                stats["subjects_created"] += 1
                
                # Create modules
                for module in subject.get("modules", []):
                    module_result = self.create_module(module, subject_code)
                    if module_result:
                        stats["modules_created"] += 1
                        
                        # Create topics
                        module_id = f"{subject_code}_M{module['number']}"
                        for topic in module.get("topics", []):
                            topic_result = self.create_topic(topic, module_id)
                            if topic_result:
                                stats["topics_created"] += 1
                
            except Exception as e:
                error_msg = f"Error loading subject {subject.get('code', 'unknown')}: {str(e)}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
        
        return stats
    
    def clear_all_data(self) -> bool:
        """Clear all data from the knowledge graph (use with caution!)"""
        if not self.driver:
            raise ConnectionError("Neo4j not connected")
        
        query = "MATCH (n) DETACH DELETE n"
        
        with self.driver.session() as session:
            session.run(query)
            return True


# Global instance
neo4j_service = Neo4jService()
