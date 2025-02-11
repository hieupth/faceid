import os
from typing import Optional, Any, List, Tuple
from qdrant_client.http import models
from qdrant_client import QdrantClient

from .interface import InterfaceDatabase


class QdrantFaceDatabase(InterfaceDatabase):
    def __init__(
        self,
        collection_name: str,
        host: Optional[str] = os.getenv("QDRANT_HOST", default="localhost"),
        port: Optional[int] = os.getenv("QDRANT_PORT", default=6333),
        url: Optional[str] = os.getenv("QDRANT_URL", default=None),
        api_key: Optional[str] = os.getenv("QDRANT_API_KEY", default=None),
    ) -> None:
        self._client = self.connect_client(host, port, url, api_key)
        self.collection_name = collection_name
        if not self._client.collection_exists(collection_name):
            self.create_colection(
                dimension=512, distance='cosine'
            )

    def connect_client(self, host, port, url, api_key):
        if url is not None and api_key is not None:
            # cloud instance
            return QdrantClient(url=url, api_key=api_key)
        elif url is not None:
            # local instance with differ url
            return QdrantClient(url=url)
        else:
            return QdrantClient(host=host, port=port)
        
    def create_colection(self, dimension=512, distance='cosine') -> None:
        # resolve distance
        if distance == 'euclidean':
            distance = models.Distance.EUCLID
        elif distance == 'dot':
            distance = models.Distance.DOT
        elif distance == 'manhattan':
            distance = models.Distance.MANHATTAN
        else: 
            distance = models.Distance.COSINE

        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=dimension, distance=distance
            ),
        )

    def insert_faces(
        self, 
        face_embs: List[Tuple[str, List[Any]]], 
        person_id: str, 
        group_id: str, 
    ):
        '''Insert list of faces of a person to collection'''
        self._client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=hash_id, 
                    vector=face_emb,
                    payload={
                        'person_id': person_id,
                        'group_id': group_id,
                    }
                ) for hash_id, face_emb in face_embs 
            ],
        )

    def delete_face(self, face_id: str, person_id: str, group_id: str):
        '''Delete a face of a given person's id or group's id in collection'''
        if group_id is None:
            if face_id is not None:
                if len(self.get_face_by_id(face_id)) == 0:
                    return {'status': 'failed', 'message': 'No face id found'} 
                self._client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.PointIdsList(
                        points=[face_id],
                    ),
                )
                return {'status': 'success'} 
            elif person_id is not None:
                if len(self.list_faces(person_id, None)) == 0:
                    return {'status': 'failed', 'message': 'No person id found'}
                self._client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.FilterSelector(filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="person_id",
                                match=models.MatchValue(value=f"{person_id}"),
                            ),
                        ])
                    ),
                )
                return {'status': 'success'}
            else:
                return {'status': 'failed', 'message': 'No face id or person id found'}
                
        elif group_id is not None:
            if person_id is not None:
                if len(self.list_faces(person_id, group_id)) == 0:
                    return {'status': 'failed', 'message': 'No person id found'}
                self._client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.FilterSelector(filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="group_id",
                                match=models.MatchValue(value=f"{group_id}"),
                            ),
                            models.FieldCondition(
                                key="person_id",
                                match=models.MatchValue(value=f"{person_id}"),
                            ),
                        ])
                    ),
                )
                return {'status': 'success'}
            else:
                if len(self.list_faces(None, group_id)) == 0:
                    return {'status': 'failed', 'message': 'No group id found'}
                self._client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.FilterSelector(filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="group_id",
                                match=models.MatchValue(value=f"{group_id}"),
                            ),
                        ])
                    ),
                )
                return {'status': 'success'}
        else:
            return {'status': 'failed', 'message': 'No group id found'}
            
    def list_faces(self, person_id: str, group_id: str):
        '''List all faces of a given person's id or group's id in collection'''
        if person_id is not None and group_id is not None:
            return self._client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="group_id", match=models.MatchValue(value=f"{group_id}")
                        ),
                        models.FieldCondition(
                            key="person_id", match=models.MatchValue(value=f"{person_id}")
                        ),
                    ],
                ),
            )
        elif person_id is None and group_id is not None:
            return self._client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="group_id", match=models.MatchValue(value=f"{group_id}")
                        ),
                    ],
                ),
            )
        elif person_id is not None and group_id is None:
            return self._client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="person_id", match=models.MatchValue(value=f"{person_id}")
                        ),
                    ],
                ),
            )
        return self._client.scroll(
            collection_name=self.collection_name,
            limit=1000,
            with_payload=True,
        )
    
    def get_face_by_id(self, face_id: str):
        '''Get a face of a given face id in collection'''
        return self._client.retrieve(
            collection_name=self.collection_name,
            ids=[face_id],
        )

    def check_face(self, face_emb, thresh):
        res = self._client.search(
            collection_name=self.collection_name, query_vector=face_emb, limit=1
        )
        output = []
        if len(res) > 0:
            for r in res:
                if r.score > thresh:
                    output.append(r)
        return output
