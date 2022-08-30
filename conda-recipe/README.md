## Conda build
In order to create conda package manually:

Run: 
```
conda build -c conda-forge -c awolny conda-recipe
```

## Release new version
1. Make sure that `bumpversion` is installed in your conda env
2. Checkout master branch
3. Run `bumpversion patch` (or `major` or `minor`) - this will bum the version in `.bumpversion.cfg` and `__version__.py` add create a new tag.
4. Run `git push && git push --tags` - this will trigger tagged travis build
5. Tagged Travis build will do the following:
    - build a new conda package 
    - deploy the new version of the conda package to anaconda cloud (make sure you have the `CONDA_UPLOAD_TOKEN` setup in Travis)
    - build docker image
    - push docker image to the registry (make sure you have `DOCKER_USERNAME` and `DOCKER_PASSWORD` setup in travis)
