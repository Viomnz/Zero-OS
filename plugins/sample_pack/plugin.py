from zero_os.types import Result

class SamplePackCapability:
    name = "sample_pack"

    def can_handle(self, task):
        return task.text.lower().startswith("sample_pack ")

    def run(self, task):
        return Result(self.name, "sample_pack plugin executed")

def get_capability():
    return SamplePackCapability()
