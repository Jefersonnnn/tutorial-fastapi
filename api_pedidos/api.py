import os
from uuid import UUID

import httpx
from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from http import HTTPStatus

from api_pedidos.esquema import Item
from api_pedidos.excecao import PedidoNaoEncontradoError, FalhaDeComunicacaoError

app = FastAPI()

# tenant e apikey fixos somente para demoinstrações
APIKEY = os.environ.get("APIKEY", "5734143a-595d-405d-9c97-6c198537108f")
TENANT_ID = os.environ.get("TENANT_ID", '21fea73c-e244-497a-8540-be0d3c583596')
MAGALU_API_URL = "localhost:8080"
MAESTRO_SERVICE_URL = f"{MAGALU_API_URL}/maestro/v1"


@app.exception_handler(PedidoNaoEncontradoError)
def tratar_erro_pedido_nao_encontrado(request: Request, exc: PedidoNaoEncontradoError):
    return JSONResponse(status_code=HTTPStatus.NOT_FOUND, content={"message": "Pedido não encontrado"})


@app.exception_handler(FalhaDeComunicacaoError)
def tratar_error_falha_de_comunicacao(request: Request, exc: FalhaDeComunicacaoError):
    return JSONResponse(status_code=HTTPStatus.BAD_GATEWAY,
                        content={"message": "Falha de comunicação com o servidor remoto"})


@app.get("/healthcheck")
async def healthcheck():
    return {"status": "ok"}


def _recupera_itens_por_pacote(uuid_do_pedido, uuid_do_pacote):
    response = httpx.get(
        f"{MAESTRO_SERVICE_URL}/orders/{uuid_do_pedido}/packages/{uuid_do_pacote}/items",
        headers={"X-Api-Key": APIKEY, "X-Tenant-Id": TENANT_ID},
    )
    response.raise_for_status()
    return [
        Item(
            sku=item["product"]["code"],
            # campos que utilizam a função get são opicionais
            description=item["product"].get("description", ""),
            image_url=item["product"].get("image_url", ""),
            reference=item["product"].get("reference", ""),
            quantity=item["quantity"],
        )
        for item in response.json()
    ]


def recuperar_itens_por_pedido(identificacao_do_pedido: UUID) -> list[Item]:
    try:
        response = httpx.get(
            f"{MAESTRO_SERVICE_URL}/orders/{identificacao_do_pedido}",
            headers={"X-Api-Key": APIKEY, "X-Tenant-Id": TENANT_ID},
        )
        response.raise_for_status()
        pacotes = response.json()["packages"]
        itens = []
        for pacote in pacotes:
            itens.extend(
                _recupera_itens_por_pacote(identificacao_do_pedido, pacote["uuid"])
            )
        return itens
    except httpx.HTTPStatusError as exc:
        # aqui poderiam ser tratados outros erros como autenticação
        if exc.response.status_code == HTTPStatus.NOT_FOUND:
            raise PedidoNaoEncontradoError() from exc
        raise exc
    except httpx.HTTPError as exc:
        raise FalhaDeComunicacaoError() from exc


@app.get("/orders/{identificacao_do_pedido}/items")
def listar_itens(itens: list[Item] = Depends(recuperar_itens_por_pedido)):
    return itens
