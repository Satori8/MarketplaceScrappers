import sys
import re

with open(r'd:\Scrappers\marketplace-scraper\scrapers\mapi_scraper\sites\allo.py', 'r', encoding='utf-8') as f:
    text = f.read()

if 'async def async_scrape_url' not in text:
    scrape_url_code = text.split('    def scrape_url(self, url: str, page: int = 1, debug: bool = False) -> dict:\n')[1]
    
    # 1. Create async signature
    async_code = '    async def async_scrape_url(\n        self,\n        url: str,\n        page: int = 1,\n        debug: bool = False,\n        proxy: str | None = None,\n    ) -> dict:\n' + scrape_url_code

    # 2. Replace _get_with_meta
    async_code = async_code.replace('_get_with_meta(', 'await _aget_with_meta(')
    async_code = async_code.replace('save_raw=debug)', 'save_raw=debug, proxy=proxy)')

    # 3. Handle ExecJS blocking
    exec_block_old = """
                # We use a wrapper function to ensure window.__ALLO__ is returned correctly
                full_js = f\"\"\"
                var window = {{}};
                var document = {{ 
                    createElement: function() {{ return {{}}; }},
                    getElementsByTagName: function() {{ return [{{ appendChild: function() {{}} }}]; }}
                }};
                var navigator = {{ userAgent: "" }};
                window.__ALLO__ = {js_value};
                \"\"\"
                full_js = full_js.encode('ascii', 'backslashreplace').decode('ascii')
                
                ctx = execjs.compile(full_js)
                
                # TO PREVENT UnicodeDecodeError on Windows pipe: 
                # We stringify the result and escape all non-ASCII characters on the Node side.
                # This ensures the STDOUT pipe only contains ASCII characters.
                eval_script = (
                    "JSON.stringify(window.__ALLO__).replace(/[\\\\u007f-\\\\uffff]/g, "
                    "function(c) { return \\"\\\\\\\\u\\" + (\\"0000\\" + c.charCodeAt(0).toString(16)).slice(-4); })"
                )
                json_str = ctx.eval(eval_script)
"""
    
    exec_block_new = """
                def run_js(val):
                    full_js = f\"\"\"
                    var window = {{}};
                    var document = {{ 
                        createElement: function() {{ return {{}}; }},
                        getElementsByTagName: function() {{ return [{{ appendChild: function() {{}} }}]; }}
                    }};
                    var navigator = {{ userAgent: "" }};
                    window.__ALLO__ = {val};
                    \"\"\"
                    full_js = full_js.encode('ascii', 'backslashreplace').decode('ascii')
                    ctx = execjs.compile(full_js)
                    eval_script = (
                        "JSON.stringify(window.__ALLO__).replace(/[\\\\u007f-\\\\uffff]/g, "
                        "function(c) { return \\"\\\\\\\\u\\" + (\\"0000\\" + c.charCodeAt(0).toString(16)).slice(-4); })"
                    )
                    return ctx.eval(eval_script)
                import asyncio
                loop = asyncio.get_running_loop()
                json_str = await loop.run_in_executor(None, run_js, js_value)
"""
    
    # We will replace the block with the run_in_executor version.
    # Because of indentation, regex might be safer.
    # Let's replace the chunk:
    async_code_pattern = r"(# We use a wrapper function.*?json_str = ctx\.eval\(eval_script\))"
    async_code = re.sub(async_code_pattern, exec_block_new.strip(), async_code, flags=re.DOTALL)

    if '_aget_with_meta' not in text:
        text = text.replace('from scrapers.mapi_scraper.http import _get_with_meta,', 'from scrapers.mapi_scraper.http import _get_with_meta, _aget_with_meta,')

    with open(r'd:\Scrappers\marketplace-scraper\scrapers\mapi_scraper\sites\allo.py', 'w', encoding='utf-8') as f:
        f.write(text + '\n' + async_code)
print('DONE')
