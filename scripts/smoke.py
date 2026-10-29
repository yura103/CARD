"""Run against a started local server: python scripts/smoke.py."""
import asyncio
import json
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    with httpx.Client(base_url="http://127.0.0.1:8000", trust_env=False) as http:
        response = http.get('/health')
        response.raise_for_status()
        assert response.json()['status'] == 'ok'
        response = http.get('/')
        response.raise_for_status()
        assert 'CardBenePICK' in response.text
    async with streamablehttp_client('http://127.0.0.1:8000/mcp') as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            expected = {'get_user_id', 'get_mcc_code', 'get_benefits_by_mcc', 'get_user_benefit_limit', 'get_sale'}
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == expected
            calls = [('get_user_id', {}), ('get_mcc_code', {'merchant': '스타벅스'}),
                     ('get_benefits_by_mcc', {'category': 'cafe'}), ('get_user_benefit_limit', {}),
                     ('get_sale', {'merchant': '스타벅스', 'amount': 8000})]
            for name, arguments in calls:
                result = await session.call_tool(name, arguments)
                assert not result.isError, result
                payload = json.loads(result.content[0].text)
                if name == 'get_sale':
                    assert payload['best_card_id'] == 'weekend'
                    assert payload['cards'][0]['discount'] == 640
                print(name, 'OK')
    print('HTTP and MCP smoke checks passed')


if __name__ == '__main__':
    asyncio.run(main())
