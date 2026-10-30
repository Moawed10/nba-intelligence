from collections.abc import Callable, Hashable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db import current_data_version, session_factory
from app.schemas.common import DataFreshness, Meta
from app.services.cache import Memo, VersionedCache
from app.services.photos import PhotoCache
from app.sync.freshness import DatasetFreshness, Freshness, dataset_freshness

# How long the data version and freshness are reused before checking the database again.
MEMO_TTL_SECONDS = 2.0
STALE = {Freshness.stale, Freshness.unavailable}


@dataclass
class ApiState:
    engine: Engine
    sessions: sessionmaker[Session] = field(init=False)
    cache: VersionedCache = field(default_factory=VersionedCache)
    version: Memo[tuple[int | None]] = field(default_factory=lambda: Memo(MEMO_TTL_SECONDS))
    freshness: Memo[dict[str, DatasetFreshness]] = field(
        default_factory=lambda: Memo(MEMO_TTL_SECONDS)
    )
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    artifacts_dir: Path = field(default_factory=lambda: get_settings().artifacts_dir)
    photos: PhotoCache = field(default_factory=lambda: PhotoCache(get_settings().photos_dir))

    def __post_init__(self) -> None:
        self.sessions = session_factory(self.engine)

    def reset(self) -> None:
        self.cache.clear()
        self.version.clear()
        self.freshness.clear()


@dataclass
class Context:
    session: Session
    state: ApiState
    response: Response

    @property
    def now(self) -> datetime:
        return self.state.clock()

    @property
    def data_version(self) -> int | None:
        return self.state.version.get(lambda: (current_data_version(self.session),))[0]

    def meta(self, dataset: str) -> Meta:
        datasets = self.state.freshness.get(
            lambda: {d.dataset: d for d in dataset_freshness(self.session, self.now)}
        )
        info = datasets[dataset]
        return Meta(
            data_freshness=DataFreshness(
                dataset=dataset,
                status=info.status,
                last_successful_sync=info.last_successful_sync,
                data_version=self.data_version,
                is_stale=info.status in STALE,
            )
        )

    def cached[T](self, namespace: str, ttl: float, key: Hashable, compute: Callable[[], T]) -> T:
        return self.state.cache.get_or_set(namespace, ttl, key, self.data_version, compute)

    def cached_model[M: BaseModel](
        self, namespace: str, ttl: float, key: Hashable, dataset: str, compute: Callable[[], M]
    ) -> M:
        """Cache the payload; freshness meta is always attached fresh."""
        value = self.cached(namespace, ttl, key, compute)
        return value.model_copy(update={"meta": self.meta(dataset)})

    def always_revalidate(self) -> None:
        """Browsers keep the response but must ask again on every load, so a refresh always shows
        the latest stored data. Repeat requests stay cheap: the server caches by data_version."""
        self.response.headers["Cache-Control"] = "no-cache"


def get_state(request: Request) -> ApiState:
    return request.app.state.api


def get_session(state: Annotated[ApiState, Depends(get_state)]) -> Iterator[Session]:
    with state.sessions() as session:
        yield session


def get_context(
    session: Annotated[Session, Depends(get_session)],
    state: Annotated[ApiState, Depends(get_state)],
    response: Response,
) -> Context:
    return Context(session=session, state=state, response=response)


Ctx = Annotated[Context, Depends(get_context)]
