#!/usr/bin/env python3

from .test_run_status import T_base

class T(T_base):

    def test_three_cells(self):
        """See doc/bug_20240315.txt
        """
        run_info = self.use_run("r84140_20240313_110906", copy=True, src="revio")
        self.md("pbpipeline")

        def gs():
            """ Clear the cache and re-read the status
            """
            run_info._clear_cache()
            return run_info.get_status()

        # Check we're all set...
        self.assertEqual(gs(), "idle_awaiting_cells")
        self.assertEqual(run_info.get_cells(), {'1_A01': run_info.CELL_PENDING,
                                                '1_B01': run_info.CELL_PENDING,
                                                '1_C01': run_info.CELL_PENDING})

        # Finish the first cell
        self.touch("pbpipeline/start_times")
        self.touch("pbpipeline/1_A01.done")
        self.touch("pbpipeline/report_upload_url.txt")

        self.assertEqual(gs(), "idle_awaiting_cells")
        self.assertEqual(run_info.get_cells(), {'1_A01': run_info.CELL_PROCESSED,
                                                '1_B01': run_info.CELL_PENDING,
                                                '1_C01': run_info.CELL_PENDING})

        # And start processing the second
        self.touch("pbpipeline/1_B01.started")
        self.assertEqual(gs(), "processing_awaiting_cells")
        self.assertEqual(run_info.get_cells(), {'1_A01': run_info.CELL_PROCESSED,
                                                '1_B01': run_info.CELL_PROCESSING,
                                                '1_C01': run_info.CELL_PENDING})

        # Now the third becomes ready, and I'm not sure what to do.
        ''' # This was passing...
        self.touch("1_C01/metadata/m84140_240313_151618_s4.transferdone")
        self.assertEqual(gs(), "cell_ready")
        self.assertEqual(run_info.get_cells(), {'1_A01': run_info.CELL_PROCESSED,
                                                '1_B01': run_info.CELL_PROCESSING,
                                                '1_C01': run_info.CELL_READY})

        # So that's all well and good but it breaks my pipeline. I need the status
        # to stick in "processing" until 1_B01 finishes. Down the line
        # I can maybe fix parallel processing but for now it's too broken.
        self.touch("1_C01/metadata/m84140_240313_151618_s4.transferdone")
        self.assertEqual(gs(), "processing")
        self.assertEqual(run_info.get_cells(), {'1_A01': run_info.CELL_PROCESSED,
                                                '1_B01': run_info.CELL_PROCESSING,
                                                '1_C01': run_info.CELL_READY})

        # Now we can process the last cell
        self.touch("pbpipeline/1_B01.done")
        self.assertEqual(gs(), "cell_ready")
        self.assertEqual(run_info.get_cells(), {'1_A01': run_info.CELL_PROCESSED,
                                                '1_B01': run_info.CELL_PROCESSED,
                                                '1_C01': run_info.CELL_READY})
        '''
