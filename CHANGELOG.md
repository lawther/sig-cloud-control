# Changelog

## 0.1.0 (2026-04-21)


### Features

* add Justfile with common development tasks ([7770f57](https://github.com/lawther/sig-cloud-control/commit/7770f5708489f75dc1021035a4f8712a0b449b52))
* add password encryption, internal client constants, and interactive CLI setup ([9c0e694](https://github.com/lawther/sig-cloud-control/commit/9c0e694cc69fd579cdcf53cbf401e4abfc64b2a7))
* add warning when overwriting config file in setup command ([10d2af7](https://github.com/lawther/sig-cloud-control/commit/10d2af70cd8d6d4978b396479d8a9a299d364179))
* **client:** mildly obfuscate hardcoded encryption key and IV ([cb12b38](https://github.com/lawther/sig-cloud-control/commit/cb12b3896448553cc9169da2c789a2f37e951f20))
* **cli:** use tomli-w for config setup and improve station_id caching ([736ce29](https://github.com/lawther/sig-cloud-control/commit/736ce29b6015fcefd43f2af382b750d13166dfd5))
* improve CLI/library UX and documentation ([ad36d9a](https://github.com/lawther/sig-cloud-control/commit/ad36d9a963de4673ce33313190c1944bbbef34d8))
* initial implementation of Sigen Cloud control library and CLI ([6eb01c8](https://github.com/lawther/sig-cloud-control/commit/6eb01c8cb1c4a213fde7f4cb15f1ef05b1b1947e))
* rename library to sig-cloud-control and update client/error names ([06e4e05](https://github.com/lawther/sig-cloud-control/commit/06e4e057d7799eb672bb00fe5f0aaadc42f6f7ca))
* setup automatic pre-commit checks with Justfile as SSOT ([2b72b78](https://github.com/lawther/sig-cloud-control/commit/2b72b78975a5f3a0372b92058aaf515c09fd7dc2))
* setup pypi packaging, apache-2.0 license, and improved cli/library ux ([8ed372c](https://github.com/lawther/sig-cloud-control/commit/8ed372c528b44c51318f88f5c30973c2d8a218ac))


### Bug Fixes

* allow longer passwords ([1706de9](https://github.com/lawther/sig-cloud-control/commit/1706de90427cf0aac6a652f1b879b613b4bd7e1d))
* **client:** await async cache loading and update tests to use AsyncMock ([cbd489f](https://github.com/lawther/sig-cloud-control/commit/cbd489fa6df4f02a495a99bf3b8061bbf278fa4d))
* explicitly pass GITHUB_TOKEN to release-please action ([a4816d0](https://github.com/lawther/sig-cloud-control/commit/a4816d0c6670bbbafca2954f6f4dd90f86cba7c7))
* Insecure Cache File Creation (TOCTOU) in SigCloudClient ([a6d6046](https://github.com/lawther/sig-cloud-control/commit/a6d604692d1ac11b217e8066343c8d0d223bae68))
* migrate to googleapis/release-please-action ([d1c881c](https://github.com/lawther/sig-cloud-control/commit/d1c881c3dbb2bbcf580cc72adb1529e7a6880a46))
* move tomli-w to cli extra and dev group, align release workflow versions ([29dbf87](https://github.com/lawther/sig-cloud-control/commit/29dbf875c7e89eae73df064f60566294f85d15e5))
* refactor Justfile for reliable error reporting and 4-space indentation ([f8e82cd](https://github.com/lawther/sig-cloud-control/commit/f8e82cd489805d4a269cbf83491eaec610b68cfa))
* refactor Justfile recipes for reliable error reporting and add linting ([ec0debc](https://github.com/lawther/sig-cloud-control/commit/ec0debcfc9672a89a841eb38e3e1665362fdba10))
* refactor precommit recipe for reliable error reporting ([8790d23](https://github.com/lawther/sig-cloud-control/commit/8790d23a8fea650d1f4a136abbd8175606451bac))
* resolve type-checking errors and improve pydantic model compatibility ([5c63575](https://github.com/lawther/sig-cloud-control/commit/5c63575637bf1b3a09765408a25d666fc0862490))


### Performance Improvements

* cache Cipher instance in SigCloudClient ([35aa2a8](https://github.com/lawther/sig-cloud-control/commit/35aa2a8686cfbe86ab6ecb379fdc78e10ed6d6ce))
* offload synchronous file I/O to thread pool in SigCloudClient ([#5](https://github.com/lawther/sig-cloud-control/issues/5)) ([0662343](https://github.com/lawther/sig-cloud-control/commit/066234365708ac98b7f900c56c58e0418a50764e))
* optimize token cache loading by removing redundant exists() check ([#8](https://github.com/lawther/sig-cloud-control/issues/8)) ([d24ad8c](https://github.com/lawther/sig-cloud-control/commit/d24ad8c21a1bf294dd114f0fee84ebbad6851a61))


### Documentation

* clarify self-consumption mode description in README ([5c5ef95](https://github.com/lawther/sig-cloud-control/commit/5c5ef952559a6219e016bedacde765dfb7624de1))
* remove obsolete stuff ([fc467c7](https://github.com/lawther/sig-cloud-control/commit/fc467c7c8c0d17de51998a1ce9e12311844d6d5a))
* update warning formatting in README and consolidate linting instructions in GEMINI.md ([cb54cc0](https://github.com/lawther/sig-cloud-control/commit/cb54cc0836725514fb0f1bda9b5fa5f629542b52))
